from typing import Dict, List, Any, Optional, Set


class StepRequirements:
    """
    Represents the requirements for a workflow step to run.
    
    This class tracks required variables, provided outputs, and determines
    if a step can run based on available variables.
    """
    
    def __init__(self):
        self.required_variables: Dict[str, Dict[str, Any]] = {}
        self.provided_outputs: Dict[str, Dict[str, Any]] = {}
        self.missing_variables: List[str] = []
    
    def add_required_variable(self, name: str, description: str = "", required: bool = True):
        """Add a required variable to the requirements"""
        self.required_variables[name] = {
            "description": description,
            "required": required
        }
    
    def add_provided_output(self, name: str, description: str = "", source_step: str = ""):
        """Add a provided output to the requirements"""
        self.provided_outputs[name] = {
            "description": description,
            "source_step": source_step
        }
    
    def check_against_available(self, available_variables: Dict[str, Any]) -> bool:
        """
        Check if all required variables are available.
        
        Args:
            available_variables: Dictionary of available variables
            
        Returns:
            True if all required variables are available, False otherwise
        """
        self.missing_variables = []
        
        for var_name, var_info in self.required_variables.items():
            if var_info["required"] and var_name not in available_variables:
                self.missing_variables.append(var_name)
        
        return len(self.missing_variables) == 0
    
    def can_run(self, available_variables: Dict[str, Any]) -> bool:
        """
        Determine if the step can run based on available variables.
        
        Args:
            available_variables: Dictionary of available variables
            
        Returns:
            True if the step can run, False otherwise
        """
        return self.check_against_available(available_variables)
    
    def get_missing_variables(self) -> List[str]:
        """Get the list of missing variables"""
        return self.missing_variables
