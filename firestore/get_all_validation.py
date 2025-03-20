# get_all_validation.py

def get_all_validation(params, user_role):
    """
    Validates the query parameters for fetching incidents.
    
    Args:
    - params (dict): The query parameters from the request.
    - user_role (str): The role of the user ("admin" or "viewer").
    
    Returns:
    - (dict, int): A tuple containing the error message and HTTP status code if validation fails, otherwise None.
    """
    valid_types = ['news', 'self-report', 'both']
    valid_self_report_status = ['all', 'new', 'rejected', 'approved']
    
    # Get the 'type' parameter with a default of 'both'
    incident_type = params.get('type', 'both')
    
    # Validate 'type' parameter
    if incident_type not in valid_types:
        return {"error": "Invalid value for 'type'. Allowed values are 'news', 'self-report', 'both'."}, 400
    
    # Get 'self_report_status' with a default value
    self_report_status = params.get('self_report_status', 'new')
    
    # Admin validation: Validate self_report_status value when used
    if user_role == 'admin' and self_report_status not in valid_self_report_status:
        return {"error": "Invalid value for 'self_report_status'. Allowed values are 'all', 'new', 'rejected', 'approved'."}, 400
    
    # Viewer validation: Only approved self-reports can be viewed
    if user_role == 'viewer' and incident_type == 'self-report' and self_report_status != 'approved':
        return {"error": "Invalid query for viewers. Only 'approved' self-report incidents can be viewed."}, 400

    return None
