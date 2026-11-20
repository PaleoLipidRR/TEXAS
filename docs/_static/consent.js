// Cookie consent and Google Analytics for the TEXAS docs, matching the root site
// (paleolipidrr.github.io, al-folio's vanilla-cookieconsent setup). The Google tag is loaded only
// after a visitor accepts analytics cookies; until then nothing is sent. The docs share the root
// site's origin, so a choice made on either site applies to both.
//
// Loaded by every Jupyter Book page (html_js_files in docs/_config.yml) and by the full-page
// explorers in docs/_static/. Inside an iframe it does nothing: the page around it already counts
// the visit and shows the banner.
(function () {
  if (window.top !== window.self) return;
  var GA_ID = "G-SZJQG5J4EX";
  var CC = "https://cdn.jsdelivr.net/npm/vanilla-cookieconsent@3.1.0/dist/";

  window.dataLayer = window.dataLayer || [];
  if (typeof window.gtag !== "function") {
    window.gtag = function () {
      window.dataLayer.push(arguments);
    };
  }
  window.gtag("consent", "default", {
    ad_storage: "denied",
    analytics_storage: "denied",
    functionality_storage: "denied",
    personalization_storage: "denied",
  });

  // The two tag scripts stay inert (type text/plain) until CookieConsent enables the
  // "analytics" category; withdrawing consent reloads the page without them.
  function blocked(attrs, text) {
    var s = document.createElement("script");
    s.type = "text/plain";
    s.setAttribute("data-category", "analytics");
    for (var k in attrs) s.setAttribute(k, attrs[k]);
    if (text) s.text = text;
    document.head.appendChild(s);
  }
  blocked({ async: "", src: "https://www.googletagmanager.com/gtag/js?id=" + GA_ID });
  // Runs only once analytics is accepted (on the first visit or any later one), so it grants
  // analytics storage itself before configuring the tag.
  blocked({}, 'window.gtag("consent", "update", { analytics_storage: "granted" }); window.gtag("js", new Date()); window.gtag("config", "' + GA_ID + '");');

  var css = document.createElement("link");
  css.rel = "stylesheet";
  css.href = CC + "cookieconsent.css";
  css.integrity = "sha256-ygRrixsQlBByBZiOcJamh7JByO9fP+/l5UPtKNJmRsE=";
  css.crossOrigin = "anonymous";
  document.head.appendChild(css);

  var js = document.createElement("script");
  js.src = CC + "cookieconsent.umd.js";
  js.integrity = "sha256-vG4vLmOB/AJbJ6awr7Wg4fxonG+fxAp4cIrbIFTvRXU=";
  js.crossOrigin = "anonymous";
  js.onload = run;
  document.head.appendChild(js);

  // vanilla-cookieconsent v3 passes its callbacks a wrapper ({cookie, changedCategories, ...}),
  // so ask the library itself which categories are accepted.
  function analyticsAccepted() {
    return window.CookieConsent.acceptedCategory("analytics");
  }
  function updateConsentMode() {
    var ok = analyticsAccepted();
    window.gtag("consent", "update", {
      analytics_storage: ok ? "granted" : "denied",
      ad_storage: "denied",
      functionality_storage: "denied",
      personalization_storage: "denied",
    });
    return ok;
  }

  function run() {
    window.CookieConsent.run({
      categories: { necessary: { enabled: true, readOnly: true }, analytics: {} },
      language: {
        default: "en",
        translations: {
          en: {
            consentModal: {
              title: "We use cookies",
              description:
                'This website uses cookies to improve your experience and analyze site traffic. By clicking "Accept all", you consent to our use of cookies.',
              acceptAllBtn: "Accept all",
              acceptNecessaryBtn: "Accept only essentials",
              showPreferencesBtn: "Manage Individual preferences",
            },
            preferencesModal: {
              title: "Manage cookie preferences",
              acceptAllBtn: "Accept all",
              acceptNecessaryBtn: "Accept only essentials",
              savePreferencesBtn: "Accept current selection",
              closeIconLabel: "Close modal",
              sections: [
                {
                  title: "Cookie usage",
                  description:
                    "We use cookies to ensure the basic functionalities of the website and to enhance your online experience. You can choose for each category to opt-in/out whenever you want.",
                },
                {
                  title: "Strictly Necessary cookies",
                  description:
                    "These cookies are essential for the proper functioning of the website. Without these cookies, the website would not work properly.",
                  linkedCategory: "necessary",
                },
                {
                  title: "Analytics cookies",
                  description: "These cookies allow us to measure traffic and analyze your behavior to improve our service.",
                  linkedCategory: "analytics",
                },
                {
                  title: "More information",
                  description:
                    'For any queries in relation to our policy on cookies and your choices, please <a class="cc-link" href="https://paleolipidrr.github.io/#contact">contact us</a>.',
                },
              ],
            },
          },
        },
      },
      onFirstConsent: function () { updateConsentMode(); },
      // Withdrawing consent reloads the page, so a Google tag that already loaded stops running.
      onChange: function () { if (!updateConsentMode()) window.location.reload(); },
    });
  }
})();
