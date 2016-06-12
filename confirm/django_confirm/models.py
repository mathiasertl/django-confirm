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

from datetime import timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.nonmultipart import MIMENonMultipart
from email.mime.base import MIMEBase

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.mail import EmailMessage
from django.db import models
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils import translation
from django.utils.crypto import get_random_string
from django.utils.crypto import salted_hmac
from django.utils.encoding import python_2_unicode_compatible

import jsonfield

from .exceptions import GpgError
from .exceptions import GpgFingerprintError
from .exceptions import GpgKeyError
from .lock import GpgLock

_default_timeout_delta = getattr(settings, 'DJANGO_CONFIRM_DEFAULT_TIMEOUT', 86400)


class GPGAlternatives(EmailMultiAlternatives):
    def __init__(self, *args, **kwargs):
        super(GPGAlternatives, self).__init__(*args, **kwargs)
        self.protocol = kwargs.pop('protocol', 'application/pgp-encrypted')

    def message(self):
        msg = super(GPGAlternatives, self).message()
        msg.set_param('protocol', self.protocol)
        return msg

def default_key():
    salt = get_random_string(32)
    value = get_random_string(64)
    return salted_hmac(salt, value).hexdigest()

def default_expires():
    return timezone.now() + timedelta(_default_timeout_delta)

def default_payload():
    return {}


@python_2_unicode_compatible
class Confirmation(models.Model):
    key = models.CharField(max_length=40, default=default_key)
    created = models.DateTimeField(auto_now_add=True)
    expires = models.DateTimeField(default=default_expires)
    purpose = models.CharField(null=True, blank=True, max_length=16)
    payload = jsonfield.JSONField(default=default_payload)

    def render(self, template):
        return render_to_string(template, self.payload)

    def get_message(self):
        """Returns the appropriate EmailMessage instance."""

        txt_template = self.payload['txt_template']
        html_template = self.payload['html_template']

        if html_template and txt_template:
            msg = EmailMultiAlternatives(
                subject=self.payload['subject'],
                body=self.render(txt_template),
                from_email=self.payload['sender'],
                to=[self.payload['recipient']]
            )
            msg.attach_alternative(self.render(html_template), 'text/html')
            return msg
        elif html_template:  # html only
            msg = EmailMessage(
                subject=self.payload['subject'],
                body=self.render(html_template),
                from_email=self.payload['sender'],
                to=[self.payload['recipient']]
            )
            msg.content_subtype = 'html'
            return msg
        elif txt_template:  # txt only
            return EmailMessage(
                subject=self.payload['subject'],
                body=self.render(txt_template),
                from_email=self.payload['sender'],
                to=[self.payload['recipient']]
            )

    def gpg_keyring(self):
        import gnupg
        return gnupg.GPG(**self.payload['gpg_opts'])

    @property
    def pgp_version(self):
        pgp_version = MIMENonMultipart('application', 'pgp-encrypted')
        pgp_version.add_header('Content-Description', 'PGP/MIME version identification')
        pgp_version.set_payload('Version: 1\n')
        return pgp_version

    def gpg_sign(self, submessage):
        gpg = self.gpg_keyring()
        signer = self.payload['gpg_sign']
        msg = GPGAlternatives(self.payload['subject'], from_email=self.payload['sender'],
                              to=[self.payload['recipient']], protocol='application/pgp-signature')

        signed_body = gpg.sign(msg.as_string(), keyid=signer, detach=True)
        if not signed_body.data:
           raise GpgError("Error signing message: %s" % signed_body.stderr)

        sig = MIMEBase(_maintype='application', _subtype='pgp-signature', name='signature.asc')
        sig.set_payload(signed_body.data)
        sig.add_header('Content-Description', 'OpenPGP digital signature')
        sig.add_header('Content-Disposition', 'attachment; filename="signature.asc"')
        del sig['Content-Transfer-Encoding']

        msg.mixed_subtype = 'signed'
        msg.attach(submessage)
        msg.attach(sig)
        return msg

    def gpg_encrypt(self, submessage):
        gpg = self.gpg_keyring()
        encrypt_to = self.payload['gpg_encrypt']
        signer = self.payload['gpg_sign']
        msg = GPGAlternatives(self.payload['subject'], from_email=self.payload['sender'],
                              to=[self.payload['recipient']])

        if encrypt_to:  # refresh key from keyservers
            # Receive key of recipient. We don't care about the result, because user might have
            # already uploaded it.
            gpg.recv_keys(settings.GPG_KEYSERVER, encrypt_to)

            # ... instead, we check if it is a known key after importing
            if encrypt_to not in [k['fingerprint'] for k in gpg.list_keys()]:
                raise GpgFingerprintError("GPG key not found on keyservers.")

        elif self.payload.get('gpg_key'):  # import bare gpg key
            imported = settings.GPG.import_keys(self.payload['gpg_key'])
            if not imported.fingerprints:
                raise GpgKeyError("GPG key could not be imported.")

            encrypt_to = imported.fingerprints[0]
            self.payload['gpg_encrypt'] = encrypt_to

            # save the payload to make sure it will always have one during confirmation
            self.save()


        # Actually encrypt the data
        encrypted_body = gpg.encrypt(submessage.as_string(), [encrypt_to], sign=signer,
                                     always_trust=True)
        if not encrypted_body.data:
            raise GpgError("Error encrypting message: %s" % encrypted_body.stderr)

        encrypted = MIMEBase(_maintype='application', _subtype='octed-stream',
                             name='encrypted.asc')
        encrypted.set_payload(encrypted_body.data)
        encrypted.add_header('Content-Description', 'OpenPGP encrypted message')
        encrypted.add_header('Content-Disposition', 'inline; filename="encrypted.asc"')

        msg.mixed_subtype = 'encrypted'
        msg.attach(self.pgp_version)
        msg.attach(encrypted)
        return msg

    def handle_gpg(self, msg):
        if isinstance(msg, EmailMultiAlternatives):
            submessage = MIMEMultipart(_subtype='alternative', _subparts=msg.message().get_payload())
        else:
            submessage = msg.message()
            # NOTE: This contains many headers that should be stripped
            raise NotImplemented("Cannot yet handle non-multipart messages")  # TODO

        if self.payload['gpg_encrypt'] or self.payload['gpg_key']:
            return self.gpg_encrypt(submessage)
        elif self.payload['gpg_sign']:
            return self.gpg_sign(submessage)
        else:
            return msg

    def handle(self):
        """Really send the message."""

        msg = self.get_message()
        if self.payload['gpg_opts']:
            with GpgLock(cache_fallback=getattr(self.backend, 'client')):
                msg = self.handle_gpg(msg)

        return msg.send()

    def send(self, recipient, subject, sender=None, txt_template=None, html_template=None,
             lang=None, extra_context=None, gpg_sign=None, gpg_encrypt=None, gpg_key=None,
             gpg_opts=None):
        """This method is intended to be called from the webserver.

        It delays to celery if appropriate or sends the message directly.

        Parameters
        ----------

        sender : str, optional
            "From" address used in the email, defaults to settings.DEFAULT_FROM_EMAIL.
        gpg_sign : str
            Fingerprint used for signing the email.
        gpg_encrypt : str
            Fingerprint used for encrypting the email.
        gpg_key : str
            Raw GPG key (will be imported, if not present in the keyring).
        """
        if not txt_template and not html_template:
            raise ValueError("Require at least one of txt_template and html_template parameters.")
        if sender is None:
            sender = settings.DEFAULT_FROM_EMAIL
        if lang is None:
            lang = translation.get_language()

        self.payload['sender'] = sender
        self.payload['recipient'] = recipient
        self.payload['subject'] = subject
        self.payload['txt_template'] = txt_template
        self.payload['html_template'] = html_template
        self.payload['lang'] = lang
        self.payload['gpg_sign'] = gpg_sign
        self.payload['gpg_encrypt'] = gpg_encrypt
        self.payload['gpg_key'] = gpg_key
        self.payload['gpg_opts'] = gpg_opts
        self.payload['extra'] = extra_context
        self.save()

        if getattr(settings, 'BROKER_URL', None):  # send with celery
            from .tasks import send_email
            send_email.delay(self.pk)
            pass
        else:  # send directly
            self.handle()

    def __str__(self):
        return '%s: %s' % (self.purpose, self.key)
