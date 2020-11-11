class InjectionError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class NonCallableProviderError(InjectionError):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class UnexpectedTypeError(InjectionError):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)