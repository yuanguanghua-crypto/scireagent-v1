"""Knowledge Graph traversal service.

Builds a subgraph around a starting entity using BFS.
Returns nodes and edges suitable for Cytoscape.js consumption.
"""
from collections import deque
from apps.knowledge.models import Application, Method, Protocol, Reference
from apps.commerce.models import Product
from apps.bridges.models import ProductMethod, MethodProtocol, ProductReference, ProductProduct


# Entity type → Model mapping
ENTITY_MODELS = {
    'product': Product,
    'application': Application,
    'method': Method,
    'protocol': Protocol,
    'reference': Reference,
}

# Traversal rules: (source_type, edge_relationship, target_type, fetch_fn)
# fetch_fn(source_id) → list of (target_id, target_label)
def _product_neighbors(pid):
    """Product → Method (via ProductMethod), Reference (via ProductReference), Product (via ProductProduct)"""
    neighbors = []
    # Product → Method
    for pm in ProductMethod.objects.filter(product_id=pid).select_related('method'):
        neighbors.append({
            'target_type': 'method',
            'target_id': pm.method.id,
            'target_label': pm.method.name,
            'target_slug': pm.method.slug,
            'relationship': 'used_in',
        })
    # Product → Reference
    for pr in ProductReference.objects.filter(product_id=pid).select_related('reference'):
        neighbors.append({
            'target_type': 'reference',
            'target_id': pr.reference.id,
            'target_label': pr.reference.title[:60],
            'target_slug': '',
            'relationship': 'cited_in',
        })
    # Product → Product (related)
    for pp in ProductProduct.objects.filter(source_product_id=pid).select_related('target_product'):
        neighbors.append({
            'target_type': 'product',
            'target_id': pp.target_product.id,
            'target_label': pp.target_product.name,
            'target_slug': pp.target_product.slug,
            'relationship': pp.relation_type,
        })
    # Reverse: Product as target
    for pp in ProductProduct.objects.filter(target_product_id=pid).select_related('source_product'):
        neighbors.append({
            'target_type': 'product',
            'target_id': pp.source_product.id,
            'target_label': pp.source_product.name,
            'target_slug': pp.source_product.slug,
            'relationship': pp.relation_type,
        })
    return neighbors


def _method_neighbors(mid):
    """Method → Application (FK reverse), Protocol (via MethodProtocol), Product (reverse ProductMethod)"""
    neighbors = []
    method = Method.objects.filter(id=mid).select_related('application').first()
    if method and method.application:
        neighbors.append({
            'target_type': 'application',
            'target_id': method.application.id,
            'target_label': method.application.name,
            'target_slug': method.application.slug,
            'relationship': 'belongs_to',
        })
    # Method → Protocol
    for mp in MethodProtocol.objects.filter(method_id=mid).select_related('protocol'):
        neighbors.append({
            'target_type': 'protocol',
            'target_id': mp.protocol.id,
            'target_label': mp.protocol.name,
            'target_slug': mp.protocol.slug,
            'relationship': 'has_protocol',
        })
    # Method → Product (reverse)
    for pm in ProductMethod.objects.filter(method_id=mid).select_related('product'):
        neighbors.append({
            'target_type': 'product',
            'target_id': pm.product.id,
            'target_label': pm.product.name,
            'target_slug': pm.product.slug,
            'relationship': 'used_by',
        })
    return neighbors


def _application_neighbors(aid):
    """Application → Method (FK reverse), ResearchGoal (FK reverse)"""
    neighbors = []
    app = Application.objects.filter(id=aid).select_related('research_goal').first()
    if app and app.research_goal:
        neighbors.append({
            'target_type': 'research_goal',
            'target_id': app.research_goal.id,
            'target_label': app.research_goal.name,
            'target_slug': app.research_goal.slug,
            'relationship': 'part_of',
        })
    # Application → Method
    for method in Method.objects.filter(application_id=aid, status='active'):
        neighbors.append({
            'target_type': 'method',
            'target_id': method.id,
            'target_label': method.name,
            'target_slug': method.slug,
            'relationship': 'has_method',
        })
    return neighbors


def _protocol_neighbors(prid):
    """Protocol → Method (FK reverse)"""
    neighbors = []
    protocol = Protocol.objects.filter(id=prid).select_related('method').first()
    if protocol and protocol.method:
        neighbors.append({
            'target_type': 'method',
            'target_id': protocol.method.id,
            'target_label': protocol.method.name,
            'target_slug': protocol.method.slug,
            'relationship': 'belongs_to',
        })
    return neighbors


def _reference_neighbors(rid):
    """Reference → Product (reverse ProductReference)"""
    neighbors = []
    for pr in ProductReference.objects.filter(reference_id=rid).select_related('product'):
        neighbors.append({
            'target_type': 'product',
            'target_id': pr.product.id,
            'target_label': pr.product.name,
            'target_slug': pr.product.slug,
            'relationship': 'cited_by',
        })
    return neighbors


def _research_goal_neighbors(rgid):
    """ResearchGoal → Application (FK reverse)"""
    neighbors = []
    for app in Application.objects.filter(research_goal_id=rgid, status='active'):
        neighbors.append({
            'target_type': 'application',
            'target_id': app.id,
            'target_label': app.name,
            'target_slug': app.slug,
            'relationship': 'has_application',
        })
    return neighbors


NEIGHBOR_FETCHERS = {
    'product': _product_neighbors,
    'method': _method_neighbors,
    'application': _application_neighbors,
    'protocol': _protocol_neighbors,
    'reference': _reference_neighbors,
    'research_goal': _research_goal_neighbors,
}


def build_graph(entity_type, entity_id, depth=3, max_nodes=50, max_edges=100):
    """Build a knowledge graph subgraph around a starting entity.

    Args:
        entity_type: Starting entity type (product, application, method, etc.)
        entity_id: Starting entity ID
        depth: Maximum traversal depth (default 3)
        max_nodes: Maximum number of nodes (default 50)
        max_edges: Maximum number of edges (default 100)

    Returns:
        dict with 'nodes' and 'edges' lists
    """
    if entity_type not in ENTITY_MODELS:
        return {'nodes': [], 'edges': []}

    model = ENTITY_MODELS[entity_type]
    entity = model.objects.filter(id=entity_id).first()
    if not entity:
        return None  # Not found

    # BFS traversal
    nodes = {}
    edges = []
    visited = set()  # (type, id) pairs
    queue = deque()  # (type, id, current_depth)

    # Add starting node
    start_key = (entity_type, entity_id)
    visited.add(start_key)
    nodes[start_key] = {
        'id': f'{entity_type}_{entity_id}',
        'type': entity_type,
        'label': getattr(entity, 'name', str(entity)),
        'slug': getattr(entity, 'slug', ''),
    }
    queue.append((entity_type, entity_id, 0))

    while queue:
        if len(nodes) >= max_nodes or len(edges) >= max_edges:
            break

        current_type, current_id, current_depth = queue.popleft()

        if current_depth >= depth:
            continue

        fetcher = NEIGHBOR_FETCHERS.get(current_type)
        if not fetcher:
            continue

        neighbors = fetcher(current_id)
        for neighbor in neighbors:
            if len(nodes) >= max_nodes or len(edges) >= max_edges:
                break

            target_key = (neighbor['target_type'], neighbor['target_id'])

            # Add edge (even if target already visited)
            edge_id = f'{current_type}_{current_id}__{neighbor["target_type"]}_{neighbor["target_id"]}_{neighbor["relationship"]}'
            edge = {
                'id': edge_id,
                'source': f'{current_type}_{current_id}',
                'target': f'{neighbor["target_type"]}_{neighbor["target_id"]}',
                'relationship': neighbor['relationship'],
            }
            # Avoid duplicate edges
            if edge['id'] not in {e['id'] for e in edges}:
                edges.append(edge)

            # Add node if not visited
            if target_key not in visited:
                visited.add(target_key)
                nodes[target_key] = {
                    'id': f'{neighbor["target_type"]}_{neighbor["target_id"]}',
                    'type': neighbor['target_type'],
                    'label': neighbor['target_label'],
                    'slug': neighbor.get('target_slug', ''),
                }
                queue.append((neighbor['target_type'], neighbor['target_id'], current_depth + 1))

    return {
        'nodes': list(nodes.values())[:max_nodes],
        'edges': edges[:max_edges],
    }
