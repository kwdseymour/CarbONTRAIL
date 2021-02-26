class UndefinedState(Exception):
    '''Exception raised when the aircraft state object is missing attributes that are required for definition of the state.'''

    def __init__(self,missing_attribute):
        self.missing_attribute = missing_attribute
        self.message = f"The '{self.missing_attribute}' attribute is missing and the aircraft state is therefore undefined. Make sure the attribute is assigned before using this function."

    def __str__(self):
        return self.message

