from django import template

register = template.Library()


@register.filter
def pesos(valor):
    """89000 -> '$89.000' (pesos colombianos, sin decimales)."""
    try:
        numero = round(float(valor))
    except (TypeError, ValueError):
        return valor
    return "$" + f"{numero:,}".replace(",", ".")


@register.filter
def iniciales(usuario):
    """Usuario -> 'DM' (primera letra del nombre y del apellido)."""
    nombre = (usuario.first_name or "").strip()
    apellido = (usuario.last_name or "").strip()
    return ((nombre[:1] + apellido[:1]) or usuario.email[:1]).upper()


@register.filter
def dato(diccionario, clave):
    """{{ valores|dato:"email" }} -> valores["email"] (vacío si no existe)."""
    try:
        return diccionario.get(clave, "")
    except AttributeError:
        return ""


@register.simple_tag
def mensajes_no_leidos(usuario):
    """Total de mensajes sin leer del usuario (contador de la barra lateral)."""
    if not getattr(usuario, "is_authenticated", False):
        return 0
    from gmf.models import Mensaje
    return Mensaje.objects.filter(destinatario=usuario, leido=False).count()


@register.filter
def kg(valor):
    """Decimal -> texto con coma y sin ceros de sobra: 62.40 -> "62,4"."""
    if valor in (None, ""):
        return "—"
    texto = f"{valor:f}"
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return texto.replace(".", ",")


@register.filter
def con_signo(valor):
    """-1.8 -> "−1,8"; 2.1 -> "+2,1"; 0 -> "0"."""
    if valor in (None, ""):
        return "—"
    if valor == 0:
        return "0"
    signo = "+" if valor > 0 else "−"
    return signo + kg(abs(valor))
