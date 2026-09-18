"""Fresh multiple-choice tasks, checked with two exact solvers per family."""

import heapq
import itertools
import math
import random
from pathlib import Path

from .common import digest, write_json, write_jsonl


def ordering(rng):
    names = list("ABCDEF")
    hidden = rng.sample(names, len(names))
    pairs = list(itertools.combinations(hidden, 2))
    constraints = rng.sample(pairs, rng.randint(5, 9))
    count = sum(all(p.index(a) < p.index(b) for a, b in constraints) for p in itertools.permutations(names))
    # Independent subset dynamic program counts linear extensions.
    dp = {frozenset(): 1}
    for size in range(len(names)):
        for done, ways in list(dp.items()):
            if len(done) == size:
                for name in set(names) - done:
                    if all(a in done for a, b in constraints if b == name):
                        nxt = done | {name}
                        dp[nxt] = dp.get(nxt, 0) + ways
    assert count == dp[frozenset(names)]
    question = "Six distinct jobs A, B, C, D, E, F must be put in a total order. "
    question += "The constraints are: " + "; ".join(f"{a} before {b}" for a, b in constraints)
    question += ". How many total orders satisfy all constraints?"
    return question, count, {"constraints": constraints, "solvers": ["permutations", "subset_dp"]}


def boolean(rng):
    names = list("PQRST")
    clauses = []
    for _ in range(rng.randint(5, 8)):
        clauses.append([(name, rng.choice([True, False])) for name in rng.sample(names, rng.randint(2, 3))])
    assignments = [dict(zip(names, bits)) for bits in itertools.product([False, True], repeat=5)]
    count = sum(all(any(a[name] == sign for name, sign in c) for c in clauses) for a in assignments)
    # Set algebra on satisfying assignments, independent of the direct evaluator.
    surviving = set(range(32))
    for clause in clauses:
        satisfying = set()
        for name, sign in clause:
            position = names.index(name)
            satisfying |= {mask for mask in range(32) if bool(mask & (1 << position)) == sign}
        surviving &= satisfying
    assert count == len(surviving)
    formula = " AND ".join("(" + " OR ".join(name if sign else f"NOT {name}" for name, sign in c) + ")" for c in clauses)
    return f"For Boolean variables P, Q, R, S, T, how many truth assignments satisfy {formula}?", count, {"clauses": clauses, "solvers": ["truth_table", "set_algebra"]}


def graph(rng):
    names = list("ABCDEFG")
    edges = {(names[i], names[i + 1]): rng.randint(1, 9) for i in range(6)}
    for a, b in itertools.combinations(names, 2):
        if rng.random() < 0.35:
            edges[a, b] = rng.randint(1, 12)
    adjacency = {n: [] for n in names}
    for (a, b), weight in edges.items():
        adjacency[a].append((b, weight))
        adjacency[b].append((a, weight))
    distance = {n: math.inf for n in names}
    distance["A"] = 0
    queue = [(0, "A")]
    while queue:
        cost, node = heapq.heappop(queue)
        if cost != distance[node]:
            continue
        for other, weight in adjacency[node]:
            if cost + weight < distance[other]:
                distance[other] = cost + weight
                heapq.heappush(queue, (cost + weight, other))

    def enumerate_paths(node, visited):
        if node == "G":
            return 0
        return min((weight + enumerate_paths(other, visited | {other}) for other, weight in adjacency[node] if other not in visited), default=math.inf)

    count = distance["G"]
    assert count == enumerate_paths("A", {"A"})
    description = ", ".join(f"{a}-{b}:{w}" for (a, b), w in sorted(edges.items()))
    return f"An undirected weighted graph has vertices A through G and exactly these edges (edge:weight): {description}. What is the shortest-path distance from A to G?", count, {"edges": [[a, b, w] for (a, b), w in edges.items()], "solvers": ["dijkstra", "all_simple_paths"]}


def generate(count=50, seed=2027):
    if count < 1:
        raise ValueError("count must be positive")
    rng = random.Random(seed)
    tasks, gold, seen = [], [], set()
    families = [("ordering", ordering), ("boolean", boolean), ("shortest_path", graph)]
    for index in range(count):
        family, factory = families[index % len(families)]
        while True:
            question, correct, witness = factory(rng)
            if question not in seen:
                break
        seen.add(question)
        numbers = {correct}
        while len(numbers) < 4:
            numbers.add(max(0, correct + rng.randint(-max(3, correct // 2), max(4, correct // 2))))
        values = sorted(numbers)
        rng.shuffle(values)
        options = dict(zip("ABCD", map(str, values)))
        task_id = f"{family}-{index:04d}"
        tasks.append({"task_id": task_id, "family": family, "question": question, "options": options})
        gold.append({"task_id": task_id, "correct_answer": next(k for k, v in options.items() if v == str(correct)), "verified_value": correct, "verification": witness})
    return tasks, gold


def save_dataset(directory, count=50, seed=2027):
    directory = Path(directory)
    if directory.exists() and any(directory.iterdir()):
        raise ValueError("Dataset directory must be empty; existing datasets are immutable")
    tasks, gold = generate(count, seed)
    write_jsonl(directory / "tasks.jsonl", tasks)
    write_jsonl(directory / "answers.jsonl", gold)
    write_json(directory / "manifest.json", {"generator": "pilot-v1", "seed": seed, "count": count, "tasks_sha256": digest(tasks), "answers_sha256": digest(gold)})
    return tasks
