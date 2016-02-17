#!/usr/bin/env python3

"""
jsonapi.asyncio.handler.relationship
====================================

:license: GNU Affero General Public License v3
"""

# std
from collections import OrderedDict

# local
from jsonapi.base import errors
from jsonapi.base import validators
from jsonapi.base.serializer import serialize_many
from .base import BaseHandler


class RelationshipHandler(BaseHandler):
    """
    Handles the relationship endpoint.
    """

    def __init__(self, api, db, request):
        """
        """
        super().__init__(api, db, request)
        self.typename = request.japi_uri_arguments.get("type")
        self.relname = request.japi_uri_arguments.get("relname")

        # Initiliased, after the resource has been loaded.
        self.real_typename = None

        # The resource is loaded in *prepare()*
        self.resource_id = self.request.japi_uri_arguments.get("id")
        self.resource = None
        return None

    async def prepare(self):
        """
        """
        if self.request.content_type[0] != "application/vnd.api+json":
            raise errors.UnsupportedMediaType()
        if not self.api.has_type(self.typename):
            raise errors.NotFound()

        # Load the resource.
        self.resource = await self.db.get((self.typename, self.resource_id))
        if self.resource is None:
            raise errors.NotFound()

        self.real_typename = self.api.get_typename(self.resource)

        # Check if the relationship exists.
        schema = self.api.get_schema(self.real_typename)
        if not self.relname in schema.relationships:
            raise errors.NotFound()

        self.relationship = schema.relationships[self.relname]
        return None

    def build_body(self):
        """
        Serializes the relationship and creates the JSONapi body.
        """
        serializer = self.api.get_serializer(self.real_typename)
        document = serializer.serialize_relationship(
            self.resource, self.relname
        )

        links = document.setdefault("links", OrderedDict())
        links["self"] = self.api.reverse_url(
            typename=self.typename, endpoint="relationship",
            id=self.resource_id, relname=self.relname
        )
        links["related"] = self.api.reverse_url(
            typename=self.typename, endpoint="related",
            id=self.resource_id, relname=self.relname
        )

        document.setdefault("jsonapi", self.api.jsonapi_object)

        body = self.api.dump_json(document)
        return body

    async def get(self):
        """
        Handles a GET request.

        http://jsonapi.org/format/#fetching-relationships
        """
        self.response.headers["content-type"] = "application/vnd.api+json"
        self.response.status_code = 200
        self.response.body = self.build_body()
        return None

    async def post(self):
        """
        Handles a POST request.

        This method is only allowed for to-many relationships.

        http://jsonapi.org/format/#crud-updating-relationships
        """
        # This method is only allowed for *to-many* relationships.
        if not self.relationship.to_many:
            raise errors.MethodNotAllowed()

        # Get the relationship document from the request.
        relationship_object = self.request.json
        validators.assert_relationship_object(relationship_object)

        # Extend the relationship.
        unserializer = self.api.get_unserializer(self.real_typename)
        await unserializer.extend_relationship(
            self.db, self.resource, self.relname, relationship_object
        )

        # Save the resource.
        self.db.save([self.resource])
        await self.db.commit()

        # Build the response
        self.response.headers["content-type"] = "application/vnd.api+json"
        self.response.status_code = 200
        self.response.body = self.build_body()
        return None

    async def patch(self):
        """
        Handles a PATCH request.

        http://jsonapi.org/format/#crud-updating-relationships
        """
        # Make sure the request contains a valid JSONapi relationship object.
        relationship_object = self.request.json
        validators.assert_relationship_object(relationship_object)

        # Patch the relationship.
        unserializer = self.api.get_unserializer(self.real_typename)
        await unserializer.update_relationship(
            self.db, self.resource, self.relname, relationship_object
        )

        # Save thte changes.
        self.db.save([self.resource])
        await self.db.commit()

        # Build the response
        self.response.headers["content-type"] = "application/vnd.api+json"
        self.response.status_code = 200
        self.response.body = self.build_body()
        return None

    async def delete(self):
        """
        Handles a DELETE request.
        """
        unserializer = self.api.get_unserializer(self.real_typename)
        unserializer.clear_relationship(self.resource, self.relname)

        # Save the changes
        self.db.save([self.resource])
        await self.db.commit()

        # Build the response
        self.response.headers["content-type"] = "application/vnd.api+json"
        self.response.status_code = 200
        self.response.body = self.build_body()
        return None