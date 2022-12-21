class InjectionError(Exception):
    pass


class NonCallableProviderError(InjectionError):
    pass


class UndeclaredProvidedTypeError(InjectionError):
    pass


class MalformedProvidedClassesError(InjectionError):
    pass


class ProviderDependencyDeadlockError(InjectionError):
    """This is raised when it's not possible to create the dependencies due to
    deadlock.

    For example:
        - Page object named "ChickenPage" require "EggPage" as a dependency.
        - Page object named "EggPage" require "ChickenPage" as a dependency.
    """

    pass
