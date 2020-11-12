class InjectionError(Exception):
    pass


class NonCallableProviderError(InjectionError):
    pass


class UndeclaredProvidedTypeError(InjectionError):
    pass


class MalformedProvidedClassesError(InjectionError):
    pass