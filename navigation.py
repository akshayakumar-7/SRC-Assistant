from collections import deque

graph = {
    "staircase": ["108"],

    "108": ["staircase", "109"],
    "109": ["108", "110"],
    "110": ["109", "111"],
    "111": ["110", "112"],
    "112": ["111", "101"],

    "101": ["112", "102"],
    "102": ["101", "103"],
    "103": ["102", "104"],
    "104": ["103", "105"],
    "105": ["104", "106"],
    "106": ["105", "107"],
    "107": ["106"]
}

room_names = {
    "108": "J.C. Bose Hall",
    "109": "B.C. Roy Hall",
    "110": "Bhaskaracharia Hall",
    "111": "Chandrasekhar Hall",
    "112": "Joseph E. Murray Hall",
    "101": "J.B.S. Haldane Hall",
    "102": "Susruta Hall",
    "103": "Aryabhata Hall",
    "104": "E. Donnall Thomas Hall",
    "105": "Brahmagupta Hall",
    "106": "Sawai Jai Singh Hall",
    "107": "M. Visvesvaraya Hall"
}

def find_path(start, end):
    queue = deque([[start]])
    visited = set()

    while queue:
        path = queue.popleft()
        node = path[-1]

        if node == end:
            return path

        if node not in visited:
            visited.add(node)

            for neighbor in graph.get(node, []):
                new_path = list(path)
                new_path.append(neighbor)
                queue.append(new_path)

    return None