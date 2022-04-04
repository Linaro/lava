from django.urls import reverse


class TestLogin:
    def test_show_login_page(self, db, client):
        ret = client.get(reverse("login"))
        assert ret.status_code == 200
