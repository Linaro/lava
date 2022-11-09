import logging

from mozilla_django_oidc.auth import OIDCAuthenticationBackend


class OIDCAuthenticationBackendUsernameFromEmail(OIDCAuthenticationBackend):
    def create_user(self, claims):
        # TODO try multiple options and fallbacks
        logger = logging.getLogger("mozilla_django_oidc")
        email = claims.get("email")
        logger.info(f"Creating new user for e-mail: {email}")
        # On Azure AD the username is not part of the claims
        username = email.split("@")[0]
        return self.UserModel.objects.create_user(username, email=email)
