"""Knowledge Graph API — /api/v1/graph/"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from apps.knowledge.services.graph_service import build_graph, ENTITY_MODELS


@api_view(['GET'])
def graph_view(request):
    """GET /api/v1/graph/?type=product&id=1&depth=3&max_nodes=50&max_edges=100

    Returns a subgraph around the specified entity.

    Query params:
        type (str): Entity type — product, application, method, protocol, reference
        id (int): Entity ID
        depth (int): Max traversal depth (default 3)
        max_nodes (int): Max nodes in result (default 50)
        max_edges (int): Max edges in result (default 100)
    """
    entity_type = request.query_params.get('type', '').strip()
    entity_id = request.query_params.get('id', '').strip()

    if not entity_type or not entity_id:
        return Response({
            'success': False,
            'data': None,
            'meta': {'error': 'Both "type" and "id" query parameters are required.'},
        }, status=status.HTTP_400_BAD_REQUEST)

    if entity_type not in ENTITY_MODELS:
        return Response({
            'success': False,
            'data': None,
            'meta': {'error': f'Invalid type "{entity_type}". Valid types: {", ".join(ENTITY_MODELS.keys())}'},
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        entity_id = int(entity_id)
    except (ValueError, TypeError):
        return Response({
            'success': False,
            'data': None,
            'meta': {'error': '"id" must be an integer.'},
        }, status=status.HTTP_400_BAD_REQUEST)

    depth = int(request.query_params.get('depth', 3))
    max_nodes = int(request.query_params.get('max_nodes', 50))
    max_edges = int(request.query_params.get('max_edges', 100))

    result = build_graph(entity_type, entity_id, depth=depth, max_nodes=max_nodes, max_edges=max_edges)

    if result is None:
        return Response({
            'success': False,
            'data': None,
            'meta': {'error': f'{entity_type} with id={entity_id} not found.'},
        }, status=status.HTTP_404_NOT_FOUND)

    return Response({
        'success': True,
        'data': result,
        'meta': {
            'entity_type': entity_type,
            'entity_id': entity_id,
            'depth': depth,
            'node_count': len(result['nodes']),
            'edge_count': len(result['edges']),
        },
    })
