#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of django-confirm (https://github.com/mathiasertl/django-confirm).
#
# django-confirm is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# django-confirm is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See
# the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with django-confirm.  If
# not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals, absolute_import

from django.db.models.query import QuerySet
from django.utils import timezone


class ConfirmationQuerySet(QuerySet):
    def valid(self):
        return self.filter(expires__gt=timezone.now())

    def expired(self):
        return self.filter(expires__lt=timezone.now())

    def purpose(self, purpose):
        return self.filter(purpose=purpose)
