/* GAWA Stats shared navigation rail.
   Add to any page with:  <script src="/nav.js" defer></script>
   To add / rename / reorder pages, edit PAGES below — nothing else. */
(function () {
  if (window.__gawaNav) return; window.__gawaNav = true;

  var PAGES = [
    { label: "Club stats",   href: "/",           match: "exact", icon: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>' },
    { label: "Post-match",     href: "/postmatch/", match: "/postmatch", icon: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V3h6v1M9 11h6M9 15h6"/>' },
    { label: "Opposition report",     href: "/opposition/", match: "/opposition", icon: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3.5"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>' },
    { label: "Quiz",           href: "/quiz/",      match: "/quiz", img: "/nav-quiz.png" }
  ];
  var LINKS = [
    { label: "Email us",       href: "mailto:admin@gawa-stats.com?subject=GAWA%20Stats%20Feedback", icon: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>' },
    { label: "Follow on X",    href: "https://x.com/GAWA_stats", external: true, icon: '<path d="M4 4l16 16M20 4L4 20"/>' }
  ];
  var W = 56, H = 32;

  var path = location.pathname.replace(/\/index\.html$/, "/");
  function isActive(p) { return p.match === "exact" ? path === "/" : path === p.match || path.indexOf(p.match + "/") === 0; }
  function svg(inner) { return '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + inner + '</svg>'; }
  function item(p, cls) {
    return '<a class="gn-item ' + cls + (p.active ? ' gn-active' : '') + '" href="' + p.href + '" data-label="' + p.label + '" aria-label="' + p.label + '"' +
      (p.active ? ' aria-current="page"' : '') + (p.external ? ' target="_blank" rel="noopener"' : '') + '>' + (p.img ? '<span class="gn-mask" style="-webkit-mask-image:url(' + p.img + ');mask-image:url(' + p.img + ')"></span>' : svg(p.icon)) + '</a>';
  }
  PAGES.forEach(function (p) { p.active = isActive(p); });

  var css = '' +
    'html.gn{padding-left:' + W + 'px;padding-top:' + H + 'px}' +
    'html.gn body>iframe{width:calc(100vw - ' + W + 'px)!important;height:calc(100vh - ' + H + 'px)!important;height:calc(100dvh - ' + H + 'px)!important}' +
    '#gb{position:fixed;top:0;left:0;right:0;height:' + H + 'px;background:#2D9858;color:#fff;display:flex;align-items:center;justify-content:center;font-family:Candara,"Trebuchet MS",Arial,sans-serif;font-size:15px;font-weight:700;letter-spacing:2px;z-index:501;text-decoration:none}' +
    'html.gn .social-links{display:none!important}' +
    '#gn{position:fixed;left:0;top:' + H + 'px;bottom:0;width:' + W + 'px;background:#0f172a;display:flex;flex-direction:column;align-items:center;padding:10px 0;gap:6px;z-index:500;font-family:Arial,sans-serif;box-shadow:2px 0 10px rgba(0,0,0,.18)}' +
    '#gn .gn-logo{width:44px;height:44px;margin:0 0 8px;display:block}' +
    '#gn .gn-logo img{width:100%;height:100%;display:block}' +
    '#gn .gn-mask{width:24px;height:24px;background:currentColor;-webkit-mask-size:contain;mask-size:contain;-webkit-mask-repeat:no-repeat;mask-repeat:no-repeat;-webkit-mask-position:center;mask-position:center;display:block}' +
    '#gn .gn-grow{flex:1}' +
    '#gn .gn-item{position:relative;width:40px;height:40px;border-radius:10px;display:flex;align-items:center;justify-content:center;color:#94a3b8;text-decoration:none;transition:background .15s,color .15s}' +
    '#gn .gn-item:hover,#gn .gn-item:focus-visible{background:#1e293b;color:#fff;outline:none}' +
    '#gn .gn-item.gn-active{background:#2D9858;color:#fff}' +
    '#gn .gn-item::after{content:attr(data-label);position:absolute;left:calc(100% + 10px);top:50%;transform:translateY(-50%);background:#111827;color:#fff;font-size:12px;white-space:nowrap;padding:5px 9px;border-radius:6px;opacity:0;pointer-events:none;transition:opacity .12s}' +
    '#gn .gn-item:hover::after,#gn .gn-item:focus-visible::after{opacity:1}' +
    '@media (max-width:700px){' +
      'html.gn{padding-left:0;padding-bottom:' + W + 'px;padding-top:' + H + 'px}' +
      'html.gn body>iframe{width:100vw!important;height:calc(100vh - ' + (W + H) + 'px)!important;height:calc(100dvh - ' + (W + H) + 'px)!important}' +
      '#gn{top:auto;width:100%;height:' + W + 'px;flex-direction:row;justify-content:space-around;padding:0 6px;gap:0;box-shadow:0 -2px 10px rgba(0,0,0,.18)}' +
      '#gn .gn-logo,#gn .gn-grow{display:none}' +
      '#gn .gn-item::after{display:none}' +
    '}';

  function mount() {
    var st = document.createElement("style"); st.id = "gn-style"; st.textContent = css; document.head.appendChild(st);
    var nav = document.createElement("nav"); nav.id = "gn"; nav.setAttribute("aria-label", "GAWA Stats");
    nav.innerHTML = '<a class="gn-logo" href="/" aria-label="GAWA Stats home"><img src="/nav-logo.png" alt=""></a>' +
      PAGES.map(function (p) { return item(p, "gn-page"); }).join("") +
      '<div class="gn-grow"></div>' +
      LINKS.map(function (p) { return item(p, "gn-link"); }).join("");
    var bar = document.createElement("a"); bar.id = "gb"; bar.href = "/"; bar.textContent = "GAWA Stats"; bar.setAttribute("aria-label", "GAWA Stats home");
    document.body.appendChild(bar);
    document.body.appendChild(nav);
    document.documentElement.classList.add("gn");
  }
  if (document.body) mount(); else document.addEventListener("DOMContentLoaded", mount);
})();
