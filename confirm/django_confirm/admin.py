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
# not, see <http://www.gnu.org/licenses/>

from __future__ import unicode_literals, absolute_import

from django.conf import settings
from django.contrib import admin

from .models import Confirmation


def resend(modeladmin, request, queryset):
    BROKER_URL = getattr(settings, 'BROKER_URL', None)

    for obj in queryset:
        if BROKER_URL:  # send via celery
            from .tasks import send_email
            send_email.delay(obj.pk)
        else:  # send directly
            obj.handle()


@admin.register(Confirmation)
class ConfirmationAdmin(admin.ModelAdmin):
    actions = [resend, ]
    list_display = ['recipient', 'purpose', 'created', 'expires', ]

    def recipient(self, obj):
        return obj.payload['recipient']
