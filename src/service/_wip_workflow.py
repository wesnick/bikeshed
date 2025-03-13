from typing import Dict, Any, Optional, List
from fastapi import Depends, HTTPException


class WorkflowEngine:
    """
    A simple workflow engine that handles state transitions based on a workflow definition.
    The workflow definition is a JSON object with the following structure:

    {
        "states": {
            "initial": {
                "transitions": {
                    "start": "in_progress"
                }
            },
            "in_progress": {
                "transitions": {
                    "complete": "completed",
                    "fail": "failed"
                }
            },
            "completed": {
                "final": true
            },
            "failed": {
                "final": true
            }
        },
        "initial_state": "initial"
    }
    """

    def __init__(self):
        pass

    def transition(self, current_state: Optional[str], transition: str, workflow_def: Dict[str, Any]) -> str:
        """
        Attempt to transition from the current state using the specified transition.

        Args:
            current_state: The current state of the workflow
            transition: The transition to attempt
            workflow_def: The workflow definition

        Returns:
            The new state after the transition

        Raises:
            HTTPException: If the transition is invalid
        """
        if not workflow_def or not isinstance(workflow_def, dict):
            raise HTTPException(status_code=400, detail="Invalid workflow definition")

        states = workflow_def.get("states", {})

        # If no current state, use initial state
        if not current_state:
            current_state = workflow_def.get("initial_state")
            if not current_state:
                raise HTTPException(status_code=400, detail="No initial state defined in workflow")
            return current_state

        # Check if current state exists
        if current_state not in states:
            raise HTTPException(status_code=400, detail=f"Invalid state: {current_state}")

        # Get current state definition
        state_def = states[current_state]

        # Check if this is a final state
        if state_def.get("final", False):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot transition from final state: {current_state}"
            )

        # Get available transitions
        transitions = state_def.get("transitions", {})

        # Check if transition is valid
        if transition not in transitions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid transition '{transition}' from state '{current_state}'. "
                       f"Available transitions: {list(transitions.keys())}"
            )

        # Get new state
        new_state = transitions[transition]

        # Validate new state
        if new_state not in states:
            raise HTTPException(status_code=500, detail=f"Transition leads to invalid state: {new_state}")

        return new_state

    def get_available_transitions(self, current_state: str, workflow_def: Dict[str, Any]) -> List[str]:
        """
        Get all available transitions from the current state.

        Args:
            current_state: The current state of the workflow
            workflow_def: The workflow definition

        Returns:
            A list of available transitions
        """
        if not workflow_def or not isinstance(workflow_def, dict):
            return []

        states = workflow_def.get("states", {})

        if not current_state or current_state not in states:
            return []

        state_def = states[current_state]

        if state_def.get("final", False):
            return []

        return list(state_def.get("transitions", {}).keys())

    def validate_workflow(self, workflow_def: Dict[str, Any]) -> bool:
        """
        Validate a workflow definition.

        Args:
            workflow_def: The workflow definition to validate

        Returns:
            True if the workflow is valid, False otherwise
        """
        if not workflow_def or not isinstance(workflow_def, dict):
            return False

        states = workflow_def.get("states", {})
        initial_state = workflow_def.get("initial_state")

        # Check if states and initial_state are defined
        if not states or not initial_state:
            return False

        # Check if initial_state exists in states
        if initial_state not in states:
            return False

        # Check all transitions lead to valid states
        for state_name, state_def in states.items():
            if not isinstance(state_def, dict):
                return False

            transitions = state_def.get("transitions", {})

            for transition, target_state in transitions.items():
                if target_state not in states:
                    return False

        return True

    def get_workflow_template(self, template_type: str = "simple") -> Dict[str, Any]:
        """
        Get a predefined workflow template.

        Args:
            template_type: The type of template to get

        Returns:
            A workflow definition
        """
        templates = {
            "simple": {
                "states": {
                    "initial": {
                        "transitions": {
                            "start": "in_progress"
                        }
                    },
                    "in_progress": {
                        "transitions": {
                            "complete": "completed",
                            "fail": "failed"
                        }
                    },
                    "completed": {
                        "final": True
                    },
                    "failed": {
                        "final": True
                    }
                },
                "initial_state": "initial"
            },
            "task_based": {
                "states": {
                    "draft": {
                        "transitions": {
                            "submit": "planning"
                        }
                    },
                    "planning": {
                        "transitions": {
                            "start": "in_progress",
                            "revise": "draft"
                        }
                    },
                    "in_progress": {
                        "transitions": {
                            "review": "review",
                            "pause": "paused"
                        }
                    },
                    "paused": {
                        "transitions": {
                            "resume": "in_progress",
                            "cancel": "cancelled"
                        }
                    },
                    "review": {
                        "transitions": {
                            "approve": "completed",
                            "reject": "in_progress"
                        }
                    },
                    "completed": {
                        "final": True
                    },
                    "cancelled": {
                        "final": True
                    }
                },
                "initial_state": "draft"
            }
        }

        return templates.get(template_type, templates["simple"])


# Dependency to inject the workflow engine
def get_workflow_engine():
    return WorkflowEngine()