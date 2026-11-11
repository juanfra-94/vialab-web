# Copia la web de Vialab (Shopify) a un sitio estático idéntico, sin Shopify.
# Corre en GitHub Actions. Salida: carpeta site/
import hashlib, os, re, json, urllib.parse
import requests
from bs4 import BeautifulSoup

BASE = "https://vialabacademy.com"
CAMPUS = "https://campus.vialabacademy.com"
OUT = "site"
S = requests.Session()
S.headers.update({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130 Safari/537.36",
                  "Accept-Language": "es-AR,es;q=0.9"})
S.cookies.set("localization", "AR", domain="vialabacademy.com")
S.cookies.set("cart_currency", "ARS", domain="vialabacademy.com")

PAGES = ["/", "/collections/all", "/collections/veterinaria", "/collections/frontpage", "/pages/contact", "/blogs/noticias",
         "/policies/privacy-policy", "/policies/refund-policy", "/policies/terms-of-service", "/policies/contact-information", "/policies/legal-notice"]
for m in re.finditer(r"<loc>([^<]+)</loc>", S.get(BASE + "/sitemap.xml").text):
    sub = S.get(m.group(1).replace("&amp;", "&")).text
    for u in re.findall(r"<loc>(https://vialabacademy\.com/[^<]*)</loc>", sub):
        p = urllib.parse.urlparse(u).path or "/"
        if p not in PAGES and not p.endswith(".md"):
            PAGES.append(p)

ASSET_HOSTS = ("vialabacademy.com/cdn/", "cdn.shopify.com/s/files/", "fonts.shopifycdn.com/", "vialabacademy.com/cdn/fonts/")
DROP_SRC = ("shopifycloud", "/checkouts/", "shop.app", "web-pixels", "/wpm/", "bugsnag", "perf-kit", "preview-bar", "theme-hot-reload",
            "shop-js", "standard-actions", "shopify-xr", "load_feature", "shopify_pay", "origin_trials", "shop_events_listener", "compiled_assets/scripts.js")
DROP_INLINE = ("ShopifyAnalytics", "__st=", "__st =", "TREKKIE", "wpmLoader", "ShopifyPay", "webmcp", "PaymentButton", "portableWallets",
               "accessToken", "shopify.content_", "featureAssets", "SignInWithShop", "Shopify.modules", "merchantCapabilities",
               "customDocumentWrite", "shopify-buyer-consent", "Shopify.shop", "(o.Shopify=o.Shopify||{}).modules", "ShopifyPaypalV4",
               "loader.init-shop", "const t='contact',e='account'", "var userAgent = navigator.userAgent", "Function.prototype.bind.bind")
assets = {}


def norm(u, page):
    u = u.strip()
    if u.startswith("//"):
        u = "https:" + u
    elif u.startswith("/"):
        u = BASE + u
    elif not u.startswith("http"):
        u = urllib.parse.urljoin(BASE + page, u)
    return u


def local(u, page="/"):
    full = norm(u, page)
    if not any(h in full for h in ASSET_HOSTS):
        return None
    if full in assets:
        return assets[full]
    path = urllib.parse.urlparse(full).path
    ext = os.path.splitext(path)[1].lower()[:6] or ".bin"
    name = "/a/" + hashlib.sha1(full.encode()).hexdigest()[:16] + ext
    assets[full] = name
    return name


def fetch_asset(full, name):
    r = S.get(full, timeout=60)
    if r.status_code != 200:
        print("asset fail", r.status_code, full)
        return
    data = r.content
    if name.endswith(".css"):
        css = r.text
        def rep(m):
            v = m.group(2).strip("'\"")
            if v.startswith("data:"):
                return m.group(0)
            ln = local(v if v.startswith(("http", "//", "/")) else urllib.parse.urljoin(full, v))
            return "url(%s)" % (ln or v)
        css = re.sub(r"url\((['\"]?)([^)]+)\)", rep, css)
        data = css.encode()
    elif name.endswith(".js"):
        data = relink(r.text, "/").encode()
    os.makedirs(os.path.dirname(OUT + name), exist_ok=True)
    open(OUT + name, "wb").write(data)


URL_RE = re.compile(r"(?:https?:)?//(?:vialabacademy\.com/cdn/|cdn\.shopify\.com/s/files/)[^\s\"'<>)\\]+")


def relink(text, page, absolute=False):
    def rep(m):
        ln = local(m.group(0), page)
        return (BASE + ln if absolute else ln) if ln else m.group(0)
    return URL_RE.sub(rep, text)


def rewrite_srcset(v, page):
    parts = []
    for item in v.split(","):
        bits = item.strip().split()
        if not bits:
            continue
        ln = local(bits[0], page)
        parts.append(" ".join([ln or bits[0]] + bits[1:]))
    return ", ".join(parts)


def page_file(p):
    p = p.rstrip("/")
    return OUT + (p + ".html" if p else "/index.html")


COUNTRY_JS = """(function(){var K='vl_country',P=location.pathname,MX=P==='/mx'||P.indexOf('/mx/')===0,H=document.documentElement;
function show(){H.style.visibility='';}
function go(c){if((c==='MX')===MX)return show();var p=MX?(P.slice(3)||'/'):('/mx'+(P==='/'?'':P));location.replace(p+location.search+location.hash);}
function save(c){try{localStorage.setItem(K,c)}catch(e){}}
window.vlSetCountry=function(c){save(c);go(c);};
var c=null;try{c=localStorage.getItem(K)}catch(e){}
if(c){go(c);return;}
H.style.visibility='hidden';var done=false;
function fin(x){if(done)return;done=true;save(x);go(x);}
setTimeout(function(){fin(MX?'MX':'AR')},2500);
fetch('https://www.cloudflare.com/cdn-cgi/trace').then(function(r){return r.text()}).then(function(t){var m=t.match(/loc=([A-Z]{2})/);fin(m&&m[1]==='MX'?'MX':'AR')}).catch(function(){fetch('https://get.geojs.io/v1/ip/country.json').then(function(r){return r.json()}).then(function(j){fin(j.country==='MX'?'MX':'AR')}).catch(function(){fin(MX?'MX':'AR')})});
})();"""
SELECTOR_JS = """<script>(function(){var sub=HTMLFormElement.prototype.submit;function pick(f){var i=f.querySelector('[name=country_code]');return i&&i.value;}
HTMLFormElement.prototype.submit=function(){if(this.classList.contains('localization-form')){var c=pick(this);if(c){window.vlSetCountry(c==='MX'?'MX':'AR');return;}}return sub.apply(this,arguments);};
document.addEventListener('submit',function(e){var f=e.target;if(f&&f.classList&&f.classList.contains('localization-form')){e.preventDefault();var c=pick(f);if(c)window.vlSetCountry(c==='MX'?'MX':'AR');}},true);})();</script>"""


def process(text, p, outfile, prefix=""):
    soup = BeautifulSoup(text, "html.parser")
    shim = soup.new_tag("script")
    shim.string = COUNTRY_JS + "window.Shopify=window.Shopify||{designMode:false,locale:'es',country:'%s',currency:{active:'%s',rate:'1.0'},routes:{root:'/'}};" % (("MX", "MXN") if prefix else ("AR", "ARS"))
    if soup.head:
        soup.head.insert(0, shim)
    for s in soup.find_all("script"):
        src = s.get("src") or ""
        txt = s.string or s.get_text() or ""
        if (src and any(d in src for d in DROP_SRC)) or (not src and any(d in txt for d in DROP_INLINE)):
            s.decompose()
            continue
        if src:
            ln = local(src, p)
            if ln:
                s["src"] = ln
        elif s.string:
            s.string = relink(s.string, p, absolute="ld+json" in (s.get("type") or ""))
    for t in soup.find_all(["link"]):
        rel = " ".join(t.get("rel") or [])
        href = t.get("href") or ""
        if any(d in href for d in DROP_SRC) or "shopify" in href and ("preconnect" in rel or "dns-prefetch" in rel):
            t.decompose()
            continue
        if href and ("stylesheet" in rel or "icon" in rel or "preload" in rel or "modulepreload" in rel):
            ln = local(href, p)
            if ln:
                t["href"] = ln
    for t in soup.find_all("meta"):
        if (t.get("name") or "").startswith("shopify") or (t.get("id") or "").startswith("shopify"):
            t.decompose()
        elif t.get("content") and ("/cdn/" in t["content"] or "cdn.shopify.com" in t["content"]):
            t["content"] = relink(t["content"], p, absolute=True)
    for t in soup.find_all("iframe"):
        if "web-pixels" in (t.get("src") or "") or "preview-bar" in (t.get("src") or ""):
            t.decompose()
    for t in soup.find_all(True):
        for attr in ("src", "data-src", "poster"):
            if t.has_attr(attr):
                ln = local(t[attr], p)
                if ln:
                    t[attr] = ln
        for attr in ("srcset", "data-srcset", "imagesrcset"):
            if t.has_attr(attr):
                t[attr] = rewrite_srcset(t[attr], p)
        if t.has_attr("style") and "url(" in t["style"]:
            t["style"] = re.sub(r"url\((['\"]?)([^)'\"]+)\1\)", lambda m: "url(%s)" % (local(m.group(2), p) or m.group(2)), t["style"])
    for st in soup.find_all("style"):
        if st.string and "url(" in st.string:
            st.string = re.sub(r"url\((['\"]?)([^)'\"]+)\1\)", lambda m: "url(%s)" % (local(m.group(2), p) or m.group(2)), st.string)
    # Shopify-only partes: selector de país, "Powered by Shopify", carrito
    for f in soup.select("form.localization-form"):
        f["action"] = "#"
        for t in f.find_all(string=True):
            if "ARS" in t and ("México" in t or (prefix and "Argentina" not in t)):
                t.replace_with(t.replace("ARS", "MXN"))
    for a in soup.find_all("a", href=True):
        h = a["href"]
        if "shopify.com" in h and "poweredby" in h:
            a.decompose()
            continue
        if "account.vialabacademy.com" in h or "aula.vialabacademy.com" in h or h.startswith("/account"):
            a["href"] = CAMPUS
        elif h.startswith(BASE):
            a["href"] = h = h[len(BASE):] or "/"
        if prefix and a.get("href", "").startswith("/") and not a["href"].startswith(("/a/", "//", prefix + "/")) and a["href"] != prefix:
            a["href"] = prefix + a["href"]
    for f in soup.select('form[action="/search"]'):
        f["action"] = "/collections/all"
    for t in soup.select('a[href="/cart"], a[href^="/cart"], #cart-icon-bubble, cart-drawer, cart-notification'):
        t.decompose()
    for f in soup.select('form[action^="/contact"]'):
        f["data-vl-contact"] = "1"
        f["action"] = "#"
    html = str(soup).replace("</body>", SELECTOR_JS + "</body>")
    # Inscripción: la transferencia de México (SPEI) llega al panel como tal
    html = html.replace('var pay = d.get("pay") === "tr" ? "transferencia" : "mercadopago";', 'var pay = d.get("pay") === "tr" ? "transferencia" : d.get("pay") === "mx" ? "transferencia mx (SPEI)" : "mercadopago";')
    # Formulario de contacto: se manda por WhatsApp (no hay servidor de Shopify)
    if 'data-vl-contact' in html:
        html = html.replace("</body>", """<script>document.querySelectorAll('[data-vl-contact]').forEach(function(f){f.addEventListener('submit',function(e){e.preventDefault();var d=new FormData(f),t=[];d.forEach(function(v,k){if(/contact\\[/.test(k)&&v)t.push(k.replace(/contact\\[|\\]/g,'')+': '+v);});window.open('https://wa.me/5493516217628?text='+encodeURIComponent('Hola Vialab Academy!\\n'+t.join('\\n')),'_blank','noopener');});});</script></body>""")
    os.makedirs(os.path.dirname(outfile), exist_ok=True)
    open(outfile, "w", encoding="utf-8").write(html)
    print("page", p)


def set_country(c):
    S.post(BASE + "/localization", data={"form_type": "localization", "utf8": "\u2713", "_method": "put", "return_to": "/", "country_code": c}, timeout=60)


for country, prefix in (("MX", "/mx"), ("AR", "")):
    set_country(country)
    for p in PAGES:
        r = S.get(BASE + p, timeout=60)
        if r.status_code != 200:
            print("skip", r.status_code, p)
            continue
        process(r.text, p, OUT + prefix + page_file(p)[len(OUT):] if prefix else page_file(p), prefix)
    r = S.get(BASE + "/pagina-que-no-existe-vialab", timeout=60)
    if r.text:
        process(r.text, prefix + "/404", OUT + prefix + "/404.html", prefix)

done = set()
while True:
    new = [(k, v) for k, v in list(assets.items()) if v not in done]
    if not new:
        break
    for full, name in new:
        done.add(name)
        fetch_asset(full, name)
print("assets", len(done))

open(OUT + "/.htaccess", "w").write("""DirectoryIndex index.html
Options -MultiViews
RewriteEngine On
RewriteCond %{HTTPS} off
RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]
RewriteCond %{HTTP_HOST} ^www\\.(.+)$ [NC]
RewriteRule ^ https://%1%{REQUEST_URI} [L,R=301]
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule ^(.+)/$ /$1 [L,R=301]
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME}.html -f
RewriteRule ^(.+)$ $1.html [L]
RewriteRule ^search$ /collections/all [L,R=302]
RewriteRule ^(cart|account|checkout)(/.*)?$ https://campus.vialabacademy.com/ [L,R=302]
ErrorDocument 404 /404.html
<IfModule mod_expires.c>
ExpiresActive On
ExpiresByType image/* "access plus 30 days"
ExpiresByType text/css "access plus 7 days"
ExpiresByType application/javascript "access plus 7 days"
</IfModule>
""")
open(OUT + "/CNAME", "w").write("nuevo.vialabacademy.com\n")
open(OUT + "/robots.txt", "w").write("User-agent: *\nAllow: /\nSitemap: https://vialabacademy.com/sitemap.xml\n")
urls = "".join("<url><loc>%s%s</loc></url>" % (BASE, p) for p in PAGES if os.path.exists(page_file(p)))
open(OUT + "/sitemap.xml", "w").write('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s</urlset>' % urls)
json.dump({"pages": PAGES, "assets": len(done)}, open(OUT + "/build.json", "w"))
