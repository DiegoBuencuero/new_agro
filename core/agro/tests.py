from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from agro.models import Moneda, Empresa


class RegistroTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.moneda = Moneda.objects.create(nombre="Real", corto="BRL")
        self.url = reverse("registro")

    def test_get_registro(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    def test_registro_exitoso(self):
        r = self.client.post(self.url, {
            "empresa_nombre":       "Test Farm",
            "empresa_razon_social": "Test Farm SA",
            "empresa_cuit":         "20-12345678-9",
            "username":             "usuarionuevo",
            "email":                "nuevo@testfarm.com",
            "password1":            "segura1234",
            "password2":            "segura1234",
        })
        self.assertRedirects(r, reverse("login"))
        user = User.objects.get(username="usuarionuevo")
        self.assertEqual(user.profile.status, "A")
        self.assertEqual(user.profile.tipo, "A")
        self.assertIsNotNone(user.profile.empresa)

    def test_registro_passwords_no_coinciden(self):
        r = self.client.post(self.url, {
            "empresa_nombre":       "Farm X",
            "empresa_razon_social": "Farm X SA",
            "empresa_cuit":         "20-99999999-9",
            "username":             "otrouser",
            "email":                "otro@farm.com",
            "password1":            "segura1234",
            "password2":            "diferente99",
        })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="otrouser").exists())

    def test_registro_username_duplicado(self):
        User.objects.create_user(username="yaexiste", password="pass1234")
        r = self.client.post(self.url, {
            "empresa_nombre":       "Farm Y",
            "empresa_razon_social": "Farm Y SA",
            "empresa_cuit":         "20-11111111-1",
            "username":             "yaexiste",
            "email":                "nuevo2@farm.com",
            "password1":            "segura1234",
            "password2":            "segura1234",
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(User.objects.filter(username="yaexiste").count(), 1)

    def test_usuario_autenticado_redirigido_desde_registro(self):
        User.objects.create_user(username="activo", password="pass1234")
        self.client.login(username="activo", password="pass1234")
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)


class MiddlewareTests(TestCase):

    def setUp(self):
        self.moneda = Moneda.objects.create(nombre="Real2", corto="BR2")
        self.empresa = Empresa.objects.create(
            nombre="Empresa Test", razon_social="ET SA",
            cuit="20-00000000-0", moneda=self.moneda, status="O",
        )

    def _crear_usuario(self, username, status):
        user = User.objects.create_user(username=username, password="pass1234")
        user.profile.empresa = self.empresa
        user.profile.status = status
        user.profile.save()
        return user

    def test_usuario_activo_accede(self):
        self._crear_usuario("activo", "A")
        self.client.login(username="activo", password="pass1234")
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)

    def test_usuario_suspendido_redirigido(self):
        self._crear_usuario("suspendido", "S")
        self.client.login(username="suspendido", password="pass1234")
        r = self.client.get("/")
        self.assertRedirects(r, reverse("cuenta_suspendida"), fetch_redirect_response=False)

    def test_usuario_pendiente_redirigido(self):
        self._crear_usuario("pendiente", "N")
        self.client.login(username="pendiente", password="pass1234")
        r = self.client.get("/")
        self.assertRedirects(r, reverse("cuenta_suspendida"), fetch_redirect_response=False)

    def test_pagina_suspendida_accesible_sin_login(self):
        r = self.client.get(reverse("cuenta_suspendida"))
        self.assertEqual(r.status_code, 200)
