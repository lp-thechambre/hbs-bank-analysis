#!/usr/bin/env python3
"""
Generate embeddings and cluster report for bank cards.

ARCHITECTURE-v1 Embedding Layer.
Calls an OpenAI-compatible embedding API to vectorize bank cards,
then clusters them and outputs cluster_report.json.

Graceful degradation:
  - Embedding API unavailable -> empty cluster report with error flag
  - sklearn not installed -> fallback to cosine similarity threshold clustering

Usage:
  python3 generate_embeddings.py --data-dir data/2026-06-02
  python3 generate_embeddings.py --data-dir data/2026-06-02 --embedding-url http://localhost:8000/v1/embeddings --model text-embedding-3-small
  python3 generate_embeddings.py --data-dir data/2026-06-02 --n-clusters 4
"""

import argparse
import json
import math
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from bank_constants import (
    EMBEDDING_API_URL, EMBEDDING_MODEL, DEFAULT_N_CLUSTERS, BANK_CODES, BANK_NAMES,
)

REQUEST_TIMEOUT = 60
MAX_RETRIES = 2


# ============================================================
# Embedding API
# ============================================================

def fetch_embeddings(texts, api_url, model=EMBEDDING_MODEL):
    """Fetch embeddings from an OpenAI-compatible embedding API.

    Returns list of embedding vectors (list of floats), or None on failure.
    """
    embeddings = []
    for i, text in enumerate(texts):
        payload = {
            "input": text,
            "model": model,
        }
        success = False
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = requests.post(api_url, json=payload, timeout=REQUEST_TIMEOUT)
                if resp.status_code == 200:
                    data = resp.json()
                    emb = data.get("data", [{}])[0].get("embedding")
                    if emb:
                        embeddings.append(emb)
                        success = True
                        break
                    else:
                        print(f"  Warning: empty embedding for text {i}", file=sys.stderr)
                else:
                    print(f"  API error {resp.status_code} for text {i}", file=sys.stderr)
            except requests.Timeout:
                print(f"  Timeout for text {i}, attempt {attempt + 1}", file=sys.stderr)
            except requests.ConnectionError:
                print(f"  Connection error for text {i}", file=sys.stderr)
            except Exception as e:
                print(f"  Error for text {i}: {e}", file=sys.stderr)

            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)

        if not success:
            print(f"Failed to embed text {i} after {MAX_RETRIES + 1} attempts", file=sys.stderr)
            return None

        # Rate limiting
        if i < len(texts) - 1:
            time.sleep(0.1)

    return embeddings


# ============================================================
# Clustering
# ============================================================

def cosine_similarity(a, b):
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0
    return dot / (norm_a * norm_b)


def cosine_distance(a, b):
    return 1 - cosine_similarity(a, b)


def kmeans_clustering(embeddings, n_clusters, max_iter=100):
    """Pure Python KMeans implementation (no sklearn dependency)."""
    import random
    random.seed(42)

    dim = len(embeddings[0])
    n = len(embeddings)

    # Initialize centroids with k-means++ seeding
    centroids = [embeddings[random.randint(0, n - 1)]]
    for _ in range(1, n_clusters):
        distances = []
        for emb in embeddings:
            min_dist = min(cosine_distance(emb, c) for c in centroids)
            distances.append(min_dist ** 2)
        total = sum(distances)
        if total == 0:
            centroids.append(embeddings[random.randint(0, n - 1)])
        else:
            r = random.random() * total
            cumulative = 0
            for i, d in enumerate(distances):
                cumulative += d
                if cumulative >= r:
                    centroids.append(embeddings[i])
                    break

    # KMeans iterations
    labels = [0] * n
    for iteration in range(max_iter):
        # Assign to nearest centroid
        changed = False
        for i, emb in enumerate(embeddings):
            best_label = min(range(n_clusters), key=lambda j: cosine_distance(emb, centroids[j]))
            if best_label != labels[i]:
                labels[i] = best_label
                changed = True

        if not changed:
            break

        # Update centroids
        for j in range(n_clusters):
            members = [embeddings[i] for i in range(n) if labels[i] == j]
            if members:
                centroids[j] = [sum(vals) / len(vals) for vals in zip(*members)]

    return labels, centroids


def compute_silhouette(embeddings, labels, n_clusters):
    """Compute silhouette score (no sklearn)."""
    n = len(embeddings)
    if n <= 1 or len(set(labels)) <= 1:
        return None

    scores = []
    for i in range(n):
        # Intra-cluster distance
        same_cluster = [j for j in range(n) if labels[j] == labels[i] and j != i]
        if same_cluster:
            a = sum(cosine_distance(embeddings[i], embeddings[j]) for j in same_cluster) / len(same_cluster)
        else:
            a = 0

        # Nearest-cluster distance
        b = float("inf")
        for c in range(n_clusters):
            if c == labels[i]:
                continue
            other_cluster = [j for j in range(n) if labels[j] == c]
            if other_cluster:
                mean_dist = sum(cosine_distance(embeddings[i], embeddings[j]) for j in other_cluster) / len(other_cluster)
                b = min(b, mean_dist)

        if b == float("inf"):
            b = 0

        max_ab = max(a, b)
        scores.append((b - a) / max_ab if max_ab > 0 else 0)

    return sum(scores) / len(scores)


def _cluster_mean_embedding(members):
    """Compute mean embedding for a cluster."""
    if not members:
        return []
    dim = len(members[0])
    return [sum(vals) / len(vals) for vals in zip(*members)]


# ============================================================
# Cluster Description
# ============================================================

def describe_cluster(member_indices, embeddings, codes):
    """Generate a human-readable label for a cluster.

    Analyzes which metrics distinguish this cluster by comparing
    cluster centroid distances to other clusters.
    """
    n = len(member_indices)
    names = [BANK_NAMES.get(codes[i], codes[i]) for i in member_indices]
    if n <= 2:
        return ", ".join(names[:3])

    # Identify bank groups in this cluster
    groups = {}
    for i in member_indices:
        code = codes[i]
        from bank_constants import BANK_GROUPS
        g = BANK_GROUPS.get(code, "unknown")
        groups[g] = groups.get(g, 0) + 1
    dominant_group = max(groups, key=groups.get) if groups else "unknown"

    group_labels = {
        "large_state_owned": "Large state-owned",
        "joint_stock": "Joint-stock",
        "city_commercial": "City commercial",
        "rural_commercial": "Rural commercial",
    }

    if groups.get(dominant_group, 0) / n >= 0.6:
        return f"{group_labels.get(dominant_group, dominant_group)} banks ({n} members)"
    else:
        return f"Mixed group ({n} banks, {len(groups)} types)"


def find_outliers(embeddings, labels, codes, threshold_multiplier=2.0):
    """Find banks that are far from their cluster centroid."""
    n_clusters = max(labels) + 1
    outliers = []

    for c in range(n_clusters):
        members = [(i, embeddings[i]) for i in range(len(embeddings)) if labels[i] == c]
        if len(members) <= 2:
            continue

        centroid = _cluster_mean_embedding([e for _, e in members])
        distances = [(i, cosine_distance(emb, centroid)) for i, emb in members]
        mean_dist = statistics.mean(d for _, d in distances)
        std_dist = statistics.stdev(d for _, d in distances) if len(distances) > 1 else 0

        for i, dist in distances:
            if std_dist > 0 and dist > mean_dist + threshold_multiplier * std_dist:
                outliers.append({
                    "code": codes[i],
                    "distance": round(dist, 4),
                    "cluster": c,
                    "reason": f"Distance {dist:.4f} > mean {mean_dist:.4f} + {threshold_multiplier}σ",
                })

    return outliers


# ============================================================
# Main Pipeline
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Generate embeddings and cluster report")
    parser.add_argument("--data-dir", required=True, help="Path to data/YYYY-MM-DD/ directory")
    parser.add_argument("--embedding-url", default=EMBEDDING_API_URL,
                        help=f"Embedding API URL (default: {EMBEDDING_API_URL})")
    parser.add_argument("--n-clusters", type=int, default=DEFAULT_N_CLUSTERS,
                        help=f"Number of clusters (default: {DEFAULT_N_CLUSTERS})")
    parser.add_argument("--model", default=EMBEDDING_MODEL,
                        help=f"Embedding model name (default: {EMBEDDING_MODEL})")
    parser.add_argument("--skip-embedding", action="store_true",
                        help="Skip embedding API call (use mock embeddings for testing)")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    cards_dir = data_dir / "cards"

    if not cards_dir.exists():
        print(f"ERROR: cards directory not found: {cards_dir}", file=sys.stderr)
        sys.exit(1)

    # Load cards
    print("Loading bank cards...", file=sys.stderr)
    codes = []
    texts = []
    for code in BANK_CODES:
        card_path = cards_dir / f"{code}.md"
        if card_path.exists():
            with open(card_path, "r", encoding="utf-8") as f:
                texts.append(f.read())
            codes.append(code)
        else:
            print(f"  Warning: card not found for {code}", file=sys.stderr)

    print(f"  Loaded {len(texts)} cards", file=sys.stderr)

    if not texts:
        print("ERROR: no cards to embed", file=sys.stderr)
        sys.exit(1)

    # Fetch embeddings
    if args.skip_embedding:
        print("  Skipping embedding API (--skip-embedding), using mock embeddings", file=sys.stderr)
        # Generate deterministic mock embeddings from text length and first chars
        import random
        random.seed(42)
        dim = 512
        embeddings = []
        for t in texts:
            seed = sum(ord(c) for c in t[:100])
            random.seed(seed)
            vec = [random.random() for _ in range(dim)]
            norm = math.sqrt(sum(v * v for v in vec))
            embeddings.append([v / norm for v in vec])
    else:
        print(f"Fetching embeddings from {args.embedding_url} (model={args.model})...", file=sys.stderr)
        embeddings = fetch_embeddings(texts, args.embedding_url, model=args.model)

    if embeddings is None:
        print("Embedding API unavailable. Generating empty cluster report.", file=sys.stderr)
        report = {
            "embedding_model": args.model,
            "embedding_api": args.embedding_url,
            "status": "error",
            "error": "Embedding API unavailable",
            "clusters": [],
            "outliers": [],
            "generated_at": datetime.now().isoformat(),
        }
    else:
        # Cluster
        print(f"Clustering {len(embeddings)} embeddings into {args.n_clusters} clusters...", file=sys.stderr)
        labels, centroids = kmeans_clustering(embeddings, args.n_clusters)
        silhouette = compute_silhouette(embeddings, labels, args.n_clusters)

        # Build cluster report
        clusters = []
        for c in range(args.n_clusters):
            member_indices = [i for i in range(len(labels)) if labels[i] == c]
            member_codes = [codes[i] for i in member_indices]
            member_names = [BANK_NAMES.get(code, code) for code in member_codes]

            clusters.append({
                "id": c,
                "size": len(member_indices),
                "members": member_codes,
                "member_names": member_names,
                "label": describe_cluster(member_indices, embeddings, codes),
            })

        # Find outliers
        outliers = find_outliers(embeddings, labels, codes)

        report = {
            "embedding_model": args.model,
            "embedding_api": args.embedding_url,
            "status": "success",
            "clustering_method": "KMeans (cosine distance)",
            "n_clusters": args.n_clusters,
            "n_banks": len(embeddings),
            "silhouette_score": round(silhouette, 4) if silhouette is not None else None,
            "clusters": clusters,
            "outliers": outliers,
            "generated_at": datetime.now().isoformat(),
        }

    # Write cluster report
    output_path = data_dir / "cluster_report.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"Cluster report saved to {output_path}", file=sys.stderr)
    print(f"  Status: {report['status']}", file=sys.stderr)
    if report.get("clusters"):
        for c in report["clusters"]:
            print(f"  Cluster {c['id']}: {c['label']} ({c['size']} banks)", file=sys.stderr)
    if report.get("outliers"):
        print(f"  Outliers: {len(report['outliers'])} banks", file=sys.stderr)
        for o in report["outliers"]:
            print(f"    {o['code']} ({BANK_NAMES.get(o['code'], '?')}): {o['reason']}", file=sys.stderr)


if __name__ == "__main__":
    main()
