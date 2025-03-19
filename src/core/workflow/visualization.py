import re
from src.models.models import Session


class WorkflowVisualizer:
    async def create_graph(self, session: Session) -> str:
        svg = session.get_graph().draw(None, prog='dot', format='svg')

        return self._clean_svg_for_web(svg.decode('utf-8'))

    @staticmethod
    def _clean_svg_for_web(svg_content):
        # Remove XML declaration
        svg_content = re.sub(r'<\?xml.*?\?>', '', svg_content)

        # Remove DOCTYPE declaration
        svg_content = re.sub(r'<!DOCTYPE[^>]*>\n?', '', svg_content)

        # Replace fixed width/height with viewBox
        width_match = re.search(r'width="(\d+)pt"', svg_content)
        height_match = re.search(r'height="(\d+)pt"', svg_content)

        if width_match and height_match:
            width = float(width_match.group(1))
            height = float(height_match.group(1))

            # Remove fixed width/height
            svg_content = re.sub(r'width="\d+pt"', '', svg_content)
            svg_content = re.sub(r'height="\d+pt"', '', svg_content)

            # Add viewBox if it doesn't exist
            if 'viewBox' not in svg_content:
                svg_content = svg_content.replace('<svg ', f'<svg viewBox="0 0 {width} {height}" ', 1)

        svg_content = re.sub(r'>\n+<', '><', svg_content)

        return svg_content.strip()
