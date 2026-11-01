from drf_spectacular.extensions import OpenApiAuthenticationExtension


class ScamShieldJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "apps.accounts.authentication.ScamShieldJWTAuthentication"
    name = "jwtAuth"

    def get_security_requirement(self, auto_schema):
        return {self.name: []}

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
