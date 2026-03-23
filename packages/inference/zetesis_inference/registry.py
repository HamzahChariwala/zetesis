from zetesis_core.interfaces import InferenceBackend


class BackendRegistry:
    _backends: dict[str, type[InferenceBackend]] = {}

    @classmethod
    def register(cls, name: str):
        def decorator(backend_cls: type[InferenceBackend]):
            cls._backends[name] = backend_cls
            return backend_cls
        return decorator

    @classmethod
    def get(cls, name: str, **kwargs) -> InferenceBackend:
        if name not in cls._backends:
            raise ValueError(f"Unknown backend: {name}. Available: {list(cls._backends.keys())}")
        return cls._backends[name](**kwargs)

    @classmethod
    def available(cls) -> list[str]:
        return list(cls._backends.keys())
