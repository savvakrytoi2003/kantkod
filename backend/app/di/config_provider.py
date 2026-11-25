from dishka import Provider, Scope, provide

from app.config.settings import Settings


class ConfigProvider(Provider):
    scope = Scope.APP

    @provide
    def settings(self) -> Settings:
        return Settings()
