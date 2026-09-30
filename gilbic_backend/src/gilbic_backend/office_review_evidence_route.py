from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute


class PrivateOfficeRoute(APIRoute):
    pragma_no_cache = False

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def protected(request: Request):
            try:
                response = await handler(request)
            except RequestValidationError as error:
                response = JSONResponse(
                    status_code=422,
                    # Pydantic errors include the rejected input, sometimes the
                    # entire private upload/review. Return field diagnostics only.
                    content=jsonable_encoder(
                        {
                            "detail": [
                                {key: item[key] for key in ("loc", "msg", "type")}
                                for item in error.errors()
                            ]
                        }
                    ),
                )
            except HTTPException as error:
                error.headers = {**(error.headers or {}), "Cache-Control": "no-store"}
                if self.pragma_no_cache:
                    error.headers["Pragma"] = "no-cache"
                raise
            response.headers["Cache-Control"] = "no-store"
            if self.pragma_no_cache:
                response.headers["Pragma"] = "no-cache"
            return response

        return protected
