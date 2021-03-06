from flask import request, jsonify, abort
from flask_restful import Resource, reqparse, current_app
from flask_principal import (
    Identity,
    AnonymousIdentity,
    RoleNeed,
    UserNeed,
    identity_changed,
    identity_loaded
)

from zou.app.utils import auth
from zou.app.services.exception import PersonNotFoundException
from zou.app.services import persons_service, auth_service
from zou.app import app
from zou.app.services.exception import (
    NoAuthStrategyConfigured,
    WrongPasswordException,
    UnactiveUserException
)


from flask_jwt_extended import (
    jwt_required,
    jwt_refresh_token_required,
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    get_raw_jwt,
    set_access_cookies,
    set_refresh_cookies,
    unset_jwt_cookies
)


def is_from_browser(user_agent):
    return user_agent.browser in [
        "camino",
        "chrome",
        "firefox",
        "galeon",
        "kmeleon",
        "konqueror",
        "links",
        "lynx",
        "msie",
        "msn",
        "netscape",
        "opera",
        "safari",
        "seamonkey",
        "webkit"
    ]


@identity_loaded.connect_via(app)
def on_identity_loaded(sender, identity):
    if identity.id is not None:
        from zou.app.services import persons_service
        identity.user = persons_service.get_person(identity.id)

        if hasattr(identity.user, "id"):
            identity.provides.add(UserNeed(identity.user.id))

        if identity.user.role == "admin":
            identity.provides.add(RoleNeed("admin"))
            identity.provides.add(RoleNeed("manager"))

        if identity.user.role == "manager":
            identity.provides.add(RoleNeed("manager"))

        return identity


class AuthenticatedResource(Resource):

    @jwt_required
    def get(self):
        try:
            person = persons_service.get_by_email(get_jwt_identity())
            return {
                "authenticated": True,
                "user": person.serialize()
            }
        except PersonNotFoundException:
            abort(401)


class LogoutResource(Resource):

    @jwt_required
    def get(self):
        try:
            current_token = get_raw_jwt()
            jti = current_token['jti']
            auth_service.revoke_tokens(app, jti)
            identity_changed.send(
                current_app._get_current_object(),
                identity=AnonymousIdentity()
            )
        except KeyError:
            return {
                "Access token not found."
            }, 500

        logout_data = {
            "logout": True
        }

        if is_from_browser(request.user_agent):
            response = jsonify(logout_data)
            unset_jwt_cookies(response)
            return response
        else:
            return logout_data


class LoginResource(Resource):

    def post(self):
        (email, password) = self.get_arguments()
        try:
            user = auth_service.check_auth(app, email, password)
            access_token = create_access_token(identity=user["email"])
            refresh_token = create_refresh_token(identity=user["email"])
            auth_service.register_tokens(app, access_token, refresh_token)
            identity_changed.send(
                current_app._get_current_object(),
                identity=Identity(user["id"])
            )

            if is_from_browser(request.user_agent):
                response = jsonify({
                    "user": user,
                    "login": True
                })
                set_access_cookies(response, access_token)
                set_refresh_cookies(response, refresh_token)

            else:
                response = {
                    "login": True,
                    "user": user,
                    "access_token": access_token,
                    "refresh_token": refresh_token
                }

            return response
        except PersonNotFoundException:
            current_app.logger.info("User is not registered.")
            return {"login": False}, 400
        except WrongPasswordException:
            current_app.logger.info("User gave a wrong password.")
            return {"login": False}, 400
        except NoAuthStrategyConfigured:
            current_app.logger.info(
                "Authentication strategy is not properly configured."
            )
            return {"login": False}, 400
        except UnactiveUserException:
            return {
                "error": True,
                "message": "Old password is wrong."
            }, 400

    def get_arguments(self):
        parser = reqparse.RequestParser()
        parser.add_argument(
            "email",
            required=True,
            help="User email is missing."
        )
        parser.add_argument("password", default="default")
        args = parser.parse_args()

        return (
            args["email"],
            args["password"],
        )


class RefreshTokenResource(Resource):

    @jwt_refresh_token_required
    def get(self):
        email = get_jwt_identity()
        access_token = create_access_token(identity=email)
        auth_service.register_tokens(app, access_token)
        if is_from_browser(request.user_agent):
            response = jsonify({'refresh': True})
            set_access_cookies(response, access_token)
        else:
            return {
                "access_token": access_token
            }


class RegistrationResource(Resource):

    def post(self):
        (
            email,
            password,
            password_2,
            first_name,
            last_name
        ) = self.get_arguments()

        try:
            email = auth.validate_email(email)
            auth.validate_password(password, password_2)
            password = auth.encrypt_password(password)
            persons_service.create_person(
                email,
                password,
                first_name,
                last_name
            )
            return {"registration_success": True}, 201
        except auth.PasswordsNoMatchException:
            return {
                "error": True,
                "message": "Confirmation password doesn't match."
            }, 400
        except auth.PasswordTooShortException:
            return {
                "error": True,
                "message": "Password is too short."
            }, 400
        except auth.EmailNotValidException as exception:
            return {
                "error": True,
                "message": str(exception)
            }, 400

    def get_arguments(self):
        parser = reqparse.RequestParser()
        parser.add_argument(
            "email",
            required=True,
            help="User email is missing."
        )
        parser.add_argument(
            "first_name",
            required=True,
            help="First name is missing."
        )
        parser.add_argument(
            "last_name",
            required=True,
            help="Last name is missing."
        )
        parser.add_argument(
            "password",
            required=True,
            help="Password is missing."
        )
        parser.add_argument(
            "password_2",
            required=True,
            help="Confirmation password is missing."
        )
        args = parser.parse_args()

        return (
            args["email"],
            args["password"],
            args["password_2"],
            args["first_name"],
            args["last_name"]
        )


class ChangePasswordResource(Resource):

    @jwt_required
    def post(self):
        (
            old_password,
            password,
            password_2,
        ) = self.get_arguments()

        try:
            auth_service.check_auth(app, get_jwt_identity(), old_password)
            auth.validate_password(password, password_2)
            password = auth.encrypt_password(password)
            persons_service.update_password(get_jwt_identity(), password)
            return {"change_password_success": True}

        except auth.PasswordsNoMatchException:
            return {
                "error": True,
                "message": "Confirmation password doesn't match."
            }, 400
        except auth.PasswordTooShortException:
            return {
                "error": True,
                "message": "Password is too short."
            }, 400
        except UnactiveUserException:
            return {
                "error": True,
                "message": "Old password is wrong."
            }, 400
        except auth.WrongPasswordException:
            return {
                "error": True,
                "message": "User is unactive."
            }, 400

    def get_arguments(self):
        parser = reqparse.RequestParser()
        parser.add_argument(
            "old_password",
            required=True,
            help="Old password is missing."
        )
        parser.add_argument(
            "password",
            required=True,
            help="New password is missing."
        )
        parser.add_argument(
            "password_2",
            required=True,
            help="New password confirmation is missing."
        )
        args = parser.parse_args()

        return (
            args["old_password"],
            args["password"],
            args["password_2"]
        )


class PersonListResource(Resource):
    """
    Resource used to list people available in the database without being logged.
    It is used currently by some studios that rely on authentication without
    password.
    """

    def get(self):
        person_names = []
        for person in persons_service.all_active():
            person_names.append({
                "id": str(person.id),
                "email": person.email,
                "first_name": person.first_name,
                "last_name": person.last_name,
                "desktop_login": person.desktop_login
            })
        return person_names
