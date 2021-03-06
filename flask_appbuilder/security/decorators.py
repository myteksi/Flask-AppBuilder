import functools
import logging

from flask import current_app, flash, jsonify, make_response, redirect, request, url_for, abort
from flask_jwt_extended import verify_jwt_in_request
from flask_login import current_user

from .._compat import as_unicode
from ..const import (
    FLAMSG_ERR_SEC_ACCESS_DENIED,
    LOGMSG_ERR_SEC_ACCESS_DENIED,
    PERMISSION_PREFIX,
)

log = logging.getLogger(__name__)


def protect(allow_browser_login=False):
    """
        Use this decorator to enable granular security permissions
        to your API methods (BaseApi and child classes).
        Permissions will be associated to a role, and roles are associated to users.

        allow_browser_login will accept signed cookies obtained from the normal MVC app::

            class MyApi(BaseApi):
                @expose('/dosonmething', methods=['GET'])
                @protect(allow_browser_login=True)
                @safe
                def do_something(self):
                    ....

                @expose('/dosonmethingelse', methods=['GET'])
                @protect()
                @safe
                def do_something_else(self):
                    ....

        By default the permission's name is the methods name.
    """

    def _protect(f):
        if hasattr(f, "_permission_name"):
            permission_str = f._permission_name
        else:
            permission_str = f.__name__

        def wraps(self, *args, **kwargs):
            # Apply method permission name override if exists
            permission_str = "{}{}".format(PERMISSION_PREFIX, f._permission_name)
            if self.method_permission_name:
                _permission_name = self.method_permission_name.get(f.__name__)
                if _permission_name:
                    permission_str = "{}{}".format(PERMISSION_PREFIX, _permission_name)
            class_permission_name = self.class_permission_name
            if permission_str not in self.base_permissions:
                return self.response_401()
            if current_app.appbuilder.sm.is_item_public(
                permission_str, class_permission_name
            ):
                return f(self, *args, **kwargs)
            if not (self.allow_browser_login or allow_browser_login):
                verify_jwt_in_request()
            if current_app.appbuilder.sm.has_access(
                permission_str, class_permission_name
            ):
                return f(self, *args, **kwargs)
            elif self.allow_browser_login or allow_browser_login:
                if not current_user.is_authenticated:
                    verify_jwt_in_request()
                if current_app.appbuilder.sm.has_access(
                    permission_str, class_permission_name
                ):
                    return f(self, *args, **kwargs)
            log.warning(
                LOGMSG_ERR_SEC_ACCESS_DENIED.format(
                    permission_str, class_permission_name
                )
            )
            return self.response_401()

        f._permission_name = permission_str
        return functools.update_wrapper(wraps, f)

    return _protect


def has_access(f):
    """
        Use this decorator to enable granular security permissions to your methods.
        Permissions will be associated to a role, and roles are associated to users.

        By default the permission's name is the methods name.
    """
    if hasattr(f, "_permission_name"):
        permission_str = f._permission_name
    else:
        permission_str = f.__name__

    def wraps(self, *args, **kwargs):
        permission_str = "{}{}".format(PERMISSION_PREFIX, f._permission_name)
        if self.method_permission_name:
            _permission_name = self.method_permission_name.get(f.__name__)
            if _permission_name:
                permission_str = "{}{}".format(PERMISSION_PREFIX, _permission_name)
        if permission_str in self.base_permissions and self.appbuilder.sm.has_access(
            permission_str, self.class_permission_name
        ):
            return f(self, *args, **kwargs)
        else:
            log.warning(
                LOGMSG_ERR_SEC_ACCESS_DENIED.format(
                    permission_str, self.__class__.__name__
                )
            )
            if current_user.is_authenticated:
                abort(404)
            else:
                flash(as_unicode(FLAMSG_ERR_SEC_ACCESS_DENIED), "danger")
                return redirect(
                    url_for(
                        self.appbuilder.sm.auth_view.__class__.__name__ + ".login",
                        next=request.url
                    )
                )

    f._permission_name = permission_str
    return functools.update_wrapper(wraps, f)


def has_access_api(f):
    """
        Use this decorator to enable granular security permissions to your API methods.
        Permissions will be associated to a role, and roles are associated to users.

        By default the permission's name is the methods name.

        this will return a message and HTTP 401 is case of unauthorized access.
    """
    if hasattr(f, "_permission_name"):
        permission_str = f._permission_name
    else:
        permission_str = f.__name__

    def wraps(self, *args, **kwargs):
        permission_str = "{}{}".format(PERMISSION_PREFIX, f._permission_name)
        if self.method_permission_name:
            _permission_name = self.method_permission_name.get(f.__name__)
            if _permission_name:
                permission_str = "{}{}".format(PERMISSION_PREFIX, _permission_name)
        if permission_str in self.base_permissions and self.appbuilder.sm.has_access(
            permission_str, self.class_permission_name
        ):
            return f(self, *args, **kwargs)
        else:
            log.warning(
                LOGMSG_ERR_SEC_ACCESS_DENIED.format(
                    permission_str, self.__class__.__name__
                )
            )
            response = make_response(
                jsonify(
                    {"message": str(FLAMSG_ERR_SEC_ACCESS_DENIED), "severity": "danger"}
                ),
                401,
            )
            response.headers["Content-Type"] = "application/json"
            return response

    f._permission_name = permission_str
    return functools.update_wrapper(wraps, f)


def permission_name(name):
    """
        Use this decorator to override the name of the permission.
        has_access will use the methods name has the permission name
        if you want to override this add this decorator to your methods.
        This is useful if you want to aggregate methods to permissions

        It will add '_permission_name' attribute to your method
        that will be inspected by BaseView to collect your view's
        permissions.

        Note that you should use @has_access to execute after @permission_name
        like on the following example.

        Use it like this to aggregate permissions for your methods::

            class MyModelView(ModelView):
                datamodel = SQLAInterface(MyModel)

                @has_access
                @permission_name('GeneralXPTO_Permission')
                @expose(url='/xpto')
                def xpto(self):
                    return "Your on xpto"

                @has_access
                @permission_name('GeneralXPTO_Permission')
                @expose(url='/xpto2')
                def xpto2(self):
                    return "Your on xpto2"


        :param name:
            The name of the permission to override
    """

    def wraps(f):
        f._permission_name = name
        return f

    return wraps
