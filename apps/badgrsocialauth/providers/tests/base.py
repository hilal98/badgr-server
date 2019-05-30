from unittest import skip

from allauth.socialaccount.tests import OAuth2TestsMixin, OAuthTestsMixin
from django.core import mail
from django.test import override_settings
from django.urls import reverse

from badgeuser.models import BadgeUser
from mainsite.tests import BadgrTestCase


class BadgrSocialAuthTestsMixin(object):
    """
    Default tests include expectations broken by BadgrAccountAdapter, and
    this overrides those to make more sense.
    """

    def login(self, resp_mock, **kwargs):
        """
        Set session BadgrApp before attempting each login.

        BadgrAccountAdapter.login assumes a BadgrApp pk is stored in the session. It looks like
        this means the BadgrSocialLogin view (which sets the session BadgrApp) is the only
        supported login flow.

        Logging out clears the session, as expected. We need to re-set session BadgrApp before
        attempting each login.

        TODO: Overriding BadgrAccountAdapter.logout to preserve session BadgrApp in the same
        way as BadgrAccountAdapter.login would solve this in another (probably more correct) way.
        """
        session = self.client.session
        session.update({
            'badgr_app_pk': self.badgr_app.pk
        })
        session.save()

        return super(BadgrSocialAuthTestsMixin, self).login(resp_mock, **kwargs)

    def assert_login_redirect(self, response):
        self.assertEqual(response.status_code, 302)
        redirect_url, query_string = response.url.split('?')
        self.assertRegex(query_string, r'^authToken=[^\s]+$')
        self.assertEqual(redirect_url, self.badgr_app.ui_login_redirect)

    def test_authentication_error(self):
        # override: base implementation looks for a particular template to be rendered.
        resp = self.client.get(reverse(self.provider.id + '_callback'))
        # Tried assertRedirects here, but don't want to couple this to the query params
        self.assertIn(self.badgr_app.ui_login_redirect, resp['Location'])

    def test_login(self):
        # override: base implementation uses assertRedirects, but we need to
        # allow for query params.
        response = self.login(self.get_mocked_response())
        self.assert_login_redirect(response)

    @skip('unused feature')
    def test_auto_signup(self):
        # override: don't test this.
        pass

    def test_signup(self):
        response = self.login(self.get_mocked_response())
        users = BadgeUser.objects.all()
        user = users.get()  # There can be only one.
        if user.verified:
            self.assert_login_redirect(response)
        else:
            self.assertRedirects(response,
                                 reverse('account_email_verification_sent'),
                                 fetch_redirect_response=False)

    def test_cached_email(self):
        self.login(self.get_mocked_response())
        users = BadgeUser.objects.all()
        user = users.get()  # There can be only one.
        self.assertEqual(len(user.cached_emails()), len(user.emailaddress_set.all()))


class BadgrOAuth2TestsMixin(BadgrSocialAuthTestsMixin, OAuth2TestsMixin):
    """
    Tests for OAuth2Provider subclasses in this application should use this
    mixin instead of OAuth2TestsMixin.
    """


class BadgrOAuthTestsMixin(BadgrSocialAuthTestsMixin, OAuthTestsMixin):
    """
    Tests for OAuthProvider subclasses in this application should use this
    mixin instead of OAuthTestsMixin.
    """


class SendsVerificationEmailMixin(object):
    def test_verification_email(self):
        # Expect this provider to send a verification email on first login
        before_count = len(mail.outbox)
        response = self.login(self.get_mocked_response())
        self.assertEqual(response.status_code, 302)  # sanity
        self.assertEqual(len(mail.outbox), before_count + 1)


@override_settings(UNSUBSCRIBE_SECRET_KEY='123a')
class BadgrSocialAuthTestCase(BadgrTestCase):
    def setUp(self):
        super(BadgrSocialAuthTestCase, self).setUp()
        self.badgr_app.ui_login_redirect = 'http://test-badgr.io/'
        self.badgr_app.save()

