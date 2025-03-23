# form_models.py
from enum import Enum
from typing import Any, Dict, List, Optional, Type, Union
from pydantic import BaseModel
import inspect
import json

class FieldType(str, Enum):
    TEXT = "text"
    NUMBER = "number"
    EMAIL = "email"
    PASSWORD = "password"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    SELECT = "select"
    TEXTAREA = "textarea"
    DATE = "date"
    FILE = "file"
    HIDDEN = "hidden"

class FormField(BaseModel):
    name: str
    label: str
    field_type: FieldType
    required: bool = True
    placeholder: Optional[str] = None
    help_text: Optional[str] = None
    options: Optional[List[Dict[str, str]]] = None  # For select, radio, etc.
    default_value: Optional[Any] = None
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    validators: Optional[List[str]] = None
    css_class: Optional[str] = None

class DynamicForm(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    fields: List[FormField]
    submit_label: str = "Submit"
    cancel_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert form to dictionary for template rendering"""
        return self.model_dump()
    
    @classmethod
    def from_pydantic(cls, model_class: Type[BaseModel], 
                     form_id: str, 
                     title: str, 
                     description: Optional[str] = None,
                     submit_label: str = "Submit",
                     cancel_url: Optional[str] = None) -> "DynamicForm":
        """Create a dynamic form from a Pydantic model"""
        fields = []
        
        for name, field in model_class.__annotations__.items():
            # Skip private fields
            if name.startswith('_'):
                continue
                
            field_info = model_class.model_fields[name]
            field_type = _get_field_type(field_info)
            
            # Get field metadata
            field_metadata = field_info.field_info.extra
            
            form_field = FormField(
                name=name,
                label=field_metadata.get('title', name.replace('_', ' ').title()),
                field_type=field_type,
                required=not field_info.allow_none,
                placeholder=field_metadata.get('description'),
                help_text=field_metadata.get('help_text'),
                default_value=field_info.default if field_info.default is not inspect.Signature.empty else None,
                min_value=field_metadata.get('ge') or field_metadata.get('gt'),
                max_value=field_metadata.get('le') or field_metadata.get('lt'),
                options=_get_field_options(field_info),
            )
            fields.append(form_field)
            
        return cls(
            id=form_id,
            title=title,
            description=description,
            fields=fields,
            submit_label=submit_label,
            cancel_url=cancel_url
        )
        
    @classmethod
    def from_json_schema(cls, schema: Dict[str, Any],
                         form_id: str,
                         title: Optional[str] = None,
                         description: Optional[str] = None,
                         submit_label: str = "Submit",
                         cancel_url: Optional[str] = None) -> "DynamicForm":
        """Create a dynamic form from a JSON Schema"""
        if isinstance(schema, str):
            schema = json.loads(schema)
            
        fields = []
        
        # Use schema title/description if not provided
        form_title = title or schema.get('title', 'Form')
        form_description = description or schema.get('description')
        
        # Process properties
        properties = schema.get('properties', {})
        required_fields = schema.get('required', [])
        
        for name, prop in properties.items():
            field_type = _json_schema_to_field_type(prop)
            
            form_field = FormField(
                name=name,
                label=prop.get('title', name.replace('_', ' ').title()),
                field_type=field_type,
                required=name in required_fields,
                placeholder=prop.get('description'),
                help_text=prop.get('description'),
                default_value=prop.get('default'),
                min_value=prop.get('minimum'),
                max_value=prop.get('maximum'),
                options=_json_schema_to_options(prop),
            )
            fields.append(form_field)
            
        return cls(
            id=form_id,
            title=form_title,
            description=form_description,
            fields=fields,
            submit_label=submit_label,
            cancel_url=cancel_url
        )

def _get_field_type(field_info) -> FieldType:
    """Determine the field type based on the Pydantic field"""
    # Check for enum types first
    if hasattr(field_info.type_, '__origin__') and field_info.type_.__origin__ is Union:
        # Handle Optional types
        non_none_types = [t for t in field_info.type_.__args__ if t is not type(None)]
        if non_none_types:
            field_info_type = non_none_types[0]
        else:
            field_info_type = str
    else:
        field_info_type = field_info.type_
        
    # Check if it's an enum
    if isinstance(field_info_type, type) and issubclass(field_info_type, Enum):
        return FieldType.SELECT
        
    # Map Python types to field types
    type_mappings = {
        str: FieldType.TEXT,
        int: FieldType.NUMBER,
        float: FieldType.NUMBER,
        bool: FieldType.CHECKBOX,
        list: FieldType.SELECT,
        dict: FieldType.TEXTAREA,
    }
    
    # Check for special field types from metadata
    field_type = field_info.field_info.extra.get('field_type')
    if field_type and field_type in FieldType.__members__:
        return FieldType(field_type)
        
    # Default mapping based on Python type
    for py_type, field_type in type_mappings.items():
        if field_info_type == py_type:
            return field_type
            
    # Default to text
    return FieldType.TEXT

def _get_field_options(field_info) -> Optional[List[Dict[str, str]]]:
    """Get options for select, radio, etc. fields"""
    # Handle Enum types
    if hasattr(field_info.type_, '__origin__') and field_info.type_.__origin__ is Union:
        # Handle Optional types
        non_none_types = [t for t in field_info.type_.__args__ if t is not type(None)]
        if non_none_types:
            field_info_type = non_none_types[0]
        else:
            return None
    else:
        field_info_type = field_info.type_
        
    if isinstance(field_info_type, type) and issubclass(field_info_type, Enum):
        return [{"value": item.value, "label": item.name} for item in field_info_type]
        
    # Check for options in field metadata
    options = field_info.field_info.extra.get('options')
    if options:
        if isinstance(options, list):
            # Handle simple list of values
            if all(isinstance(opt, (str, int, float)) for opt in options):
                return [{"value": str(opt), "label": str(opt)} for opt in options]
            # Handle list of dicts
            elif all(isinstance(opt, dict) and 'value' in opt and 'label' in opt for opt in options):
                return options
    
    return None

def _json_schema_to_field_type(prop: Dict[str, Any]) -> FieldType:
    """Convert JSON Schema type to form field type"""
    prop_type = prop.get('type', 'string')
    
    # Handle enum types
    if 'enum' in prop:
        return FieldType.SELECT
        
    # Handle specific formats
    if prop_type == 'string':
        format_type = prop.get('format', '')
        if format_type == 'email':
            return FieldType.EMAIL
        elif format_type == 'date':
            return FieldType.DATE
        elif format_type == 'password':
            return FieldType.PASSWORD
        elif prop.get('maxLength', 0) > 100:
            return FieldType.TEXTAREA
        return FieldType.TEXT
        
    # Map JSON Schema types to field types
    type_mappings = {
        'number': FieldType.NUMBER,
        'integer': FieldType.NUMBER,
        'boolean': FieldType.CHECKBOX,
        'array': FieldType.SELECT,
        'object': FieldType.TEXTAREA,
    }
    
    return type_mappings.get(prop_type, FieldType.TEXT)

def _json_schema_to_options(prop: Dict[str, Any]) -> Optional[List[Dict[str, str]]]:
    """Extract options from JSON Schema for enum types"""
    if 'enum' in prop:
        enum_values = prop['enum']
        # If there are enum_names, use them as labels
        enum_names = prop.get('enumNames', [])
        
        if enum_names and len(enum_names) == len(enum_values):
            return [{"value": str(val), "label": name} for val, name in zip(enum_values, enum_names)]
        else:
            return [{"value": str(val), "label": str(val)} for val in enum_values]
            
    # Handle oneOf as a form of enum
    if 'oneOf' in prop:
        options = []
        for option in prop['oneOf']:
            if 'const' in option and 'title' in option:
                options.append({"value": str(option['const']), "label": option['title']})
        if options:
            return options
            
    return None
