import re
from typing import Optional

from transitions.core import State, Transition

from src.models.models import Session
from src.service.logging import logger


class BikeShedState(State):

    def __init__(self, name, label=..., on_enter=..., on_exit=..., ignore_invalid_triggers=..., final=...):
        self.label = label
        super().__init__(name, on_enter, on_exit, ignore_invalid_triggers, final)


class BikeShedTransition(Transition):

    def __init__(self, source, dest, label=..., conditions=..., unless=..., before=..., after=..., prepare=...):
        self.label = label
        super().__init__(source, dest, conditions, unless, before, after, prepare)


class WorkflowVisualizer:
    """Generates visual representations of workflow state machines"""

    @staticmethod
    async def create_graph(session: Session) -> Optional[str]:
        """
        Create an SVG graph visualization of the workflow
        
        Args:
            session: The session containing the workflow state machine
            
        Returns:
            SVG representation of the workflow graph
        """
        try:
            svg = session.get_graph().draw(None, prog='dot', format='svg')
            return WorkflowVisualizer._clean_svg_for_web(svg.decode('utf-8'))

        except Exception as e:
            logger.error(f"Error creating workflow graph: {e}")
            return None

    @staticmethod
    def _clean_svg_for_web(svg_content):
        """Clean SVG content for web display"""
        if not svg_content:
            return ""
            
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
