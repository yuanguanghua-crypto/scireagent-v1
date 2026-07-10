from rest_framework.renderers import JSONRenderer


class EnvelopeRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        response = renderer_context.get('response')

        if response is not None and hasattr(response, 'data'):
            status_code = response.status_code
            if isinstance(data, dict) and 'success' in data:
                # Already wrapped
                pass
            elif status_code >= 400:
                data = {
                    'success': False,
                    'data': None,
                    'meta': {'error': data} if not isinstance(data, dict) or 'error' not in data else {'error': data.get('error', data)},
                }
            else:
                # Extract pagination meta if present
                meta = {}
                if isinstance(data, dict) and 'results' in data:
                    meta['pagination'] = {
                        'count': data.get('count'),
                        'next': data.get('next'),
                        'previous': data.get('previous'),
                    }
                    data = data['results']

                data = {
                    'success': True,
                    'data': data,
                    'meta': meta,
                }

        return super().render(data, accepted_media_type, renderer_context)
