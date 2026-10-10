import { api } from "./api.js";
import { Icon } from "./icons.jsx";
import { go } from "./nav.js";
import { AcceptInvite } from "./pages/AcceptInvite.jsx";
import { Auth } from "./pages/Auth.jsx";
import { Grocery } from "./pages/Grocery.jsx";
import { IngredientReview } from "./pages/IngredientReview.jsx";
import { RecipeFlags } from "./pages/RecipeFlags.jsx";
import { Kitchen } from "./pages/Kitchen.jsx";
import { More } from "./pages/More.jsx";
import { NewRecipe } from "./pages/NewRecipe.jsx";
import { Plan } from "./pages/Plan.jsx";
import { Privacy } from "./pages/Privacy.jsx";
import { Support } from "./pages/Support.jsx";
import { Prep } from "./pages/Prep.jsx";
import { Recipe } from "./pages/Recipe.jsx";
import { Recipes } from "./pages/Recipes.jsx";
import { ResetPassword } from "./pages/ResetPassword.jsx";
import { AccountSecurity, Filters, Newsletter, Settings, Social } from "./pages/Settings.jsx";
import { TasteLab } from "./pages/TasteLab.jsx";
import { Tour } from "./Tour.jsx";
import { useEffect, useState } from "react";

function parsePath(pathname) {
  const parts = pathname.replace(/\/+$/, "").split("/").filter(Boolean);
  if (parts.length === 0) return { page: "plan" };
  if (parts[0] === "login") return { page: "login" };
  if (parts[0] === "privacy") return { page: "privacy" };
  if (parts[0] === "support") return { page: "support" };
  if (parts[0] === "join" && parts[1]) return { page: "join", token: parts[1] };
  if (parts[0] === "reset" && parts[1]) return { page: "reset", token: parts[1] };
  if (parts[0] === "recipes" && parts[1] === "new") return { page: "new-recipe" };
  if (parts[0] === "recipes" && parts[1]) return { page: "recipe", id: Number(parts[1]) };
  if (parts[0] === "recipes") return { page: "recipes" };
  if (parts[0] === "grocery") return { page: "grocery" };
  if (parts[0] === "prep") return { page: "prep" };
  if (parts[0] === "more") return { page: "more" };
  if (parts[0] === "settings") {
    if (parts[1] === "ingredients") return { page: "ingredient-review" };
    if (parts[1] === "recipe-flags") return { page: "recipe-flags" };
    if (parts[1] === "tastelab") return { page: "taste-lab" };
    if (parts[1] === "filters") return { page: "filters" };
    if (parts[1] === "social") return { page: "social" };
    if (parts[1] === "newsletter") return { page: "newsletter" };
    if (parts[1] === "account") return { page: "account-security" };
    return { page: "settings" };
  }
  if (parts[0] === "kitchen") {
    if (parts[1] === "pantry" && parts[2] === "add") return { page: "kitchen", view: "pantry-add" };
    if (parts[1] === "pantry") return { page: "kitchen", view: "pantry" };
    if (parts[1] === "always-checked" || parts[1] === "never-shop") {
      return { page: "kitchen", view: "always-checked" };
    }
    if (parts[1] === "overrides") return { page: "kitchen", view: "overrides" };
    if (parts[1] === "stores") return { page: "kitchen", view: "stores" };
    if (parts[1] === "aisles") return { page: "kitchen", view: "aisles" };
    if (parts[1] === "templates") return { page: "kitchen", view: "templates" };
    return { page: "kitchen", view: "hub" };
  }
  return { page: "plan" };
}

function isOn(page, key) {
  if (key === "recipes") return page === "recipes" || page === "recipe" || page === "new-recipe";
  if (key === "kitchen") return page === "kitchen";
  if (key === "settings") {
    return (
      page === "settings" ||
      page === "filters" ||
      page === "social" ||
      page === "newsletter" ||
      page === "account-security" ||
      page === "ingredient-review" ||
      page === "recipe-flags" ||
      page === "taste-lab"
    );
  }
  if (key === "more-tab") {
    return (
      page === "more" ||
      page === "settings" ||
      page === "filters" ||
      page === "social" ||
      page === "newsletter" ||
      page === "account-security" ||
      page === "ingredient-review" ||
      page === "recipe-flags" ||
      page === "taste-lab" ||
      page === "kitchen" ||
      page === "prep"
    );
  }
  return page === key;
}

function NavLink({ href, navKey, label, icon, page, className = "" }) {
  return (
    <a
      href={href}
      aria-current={isOn(page, navKey) ? "page" : undefined}
      className={`nav-link${isOn(page, navKey) ? " is-on" : ""}${className ? ` ${className}` : ""}`}
      onClick={(e) => {
        e.preventDefault();
        go(href);
        window.dispatchEvent(new Event("dinnerdesk-tab-root"));
      }}
    >
      {icon ? <Icon name={icon} /> : null}
      <span>{label}</span>
    </a>
  );
}

export function App() {
  const [tabRootVersion, setTabRootVersion] = useState(0);
  useEffect(() => {
    const reset = () => setTabRootVersion((value) => value + 1);
    window.addEventListener("dinnerdesk-tab-root", reset);
    return () => window.removeEventListener("dinnerdesk-tab-root", reset);
  }, []);
  const [route, setRoute] = useState(() => parsePath(window.location.pathname));
  const [tasteHome, setTasteHome] = useState(true);
  const [authStatus, setAuthStatus] = useState(null);
  const [fatalError, setFatalError] = useState("");
  const [guestNoticeDismissed, setGuestNoticeDismissed] = useState(false);

  useEffect(() => {
    const fail = (event) => {
      if (event.reason?.name === "AbortError") return;
      setFatalError(event.detail || event.reason?.message || event.error?.message || event.message || "Unexpected application error");
    };
    window.addEventListener("dinnerdesk-failure", fail);
    window.addEventListener("unhandledrejection", fail);
    window.addEventListener("error", fail);
    return () => {
      window.removeEventListener("dinnerdesk-failure", fail);
      window.removeEventListener("unhandledrejection", fail);
      window.removeEventListener("error", fail);
    };
  }, []);

  useEffect(() => {
    api.auth
      .status()
      .then(setAuthStatus)
      .catch((e) => setFatalError(e.message));
  }, []);

  useEffect(() => {
    const onPop = () => setRoute(parsePath(window.location.pathname));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  useEffect(() => {
    const onMsg = (e) => {
      if (e.data?.type === "taste-lab") setTasteHome(Boolean(e.data.home));
    };
    window.addEventListener("message", onMsg);
    return () => window.removeEventListener("message", onMsg);
  }, []);

  const page = route.page;
  const admin = Boolean(authStatus && authStatus.admin);

  function refreshAuth() {
    api.auth
      .status()
      .then(setAuthStatus)
      .catch((e) => setFatalError(e.message));
  }

  useEffect(() => {
    if (page !== "taste-lab") setTasteHome(true);
  }, [page]);

  useEffect(() => {
    if (!admin && (page === "ingredient-review" || page === "recipe-flags")) {
      go("/settings");
    }
  }, [admin, page]);

  if (page === "privacy") return <Privacy />;
  if (page === "support") return <Support />;

  if (fatalError) return <main role="alert" className="screen pad"><h1>App stopped</h1><pre>{fatalError}</pre></main>;

  if (authStatus === null) {
    return <div className="app is-auth" />;
  }

  if (page === "join") {
    return (
      <AcceptInvite
        token={route.token}
        onAuthed={() => {
          refreshAuth();
          go("/settings/account");
        }}
      />
    );
  }

  if (page === "reset") {
    return (
      <ResetPassword
        token={route.token}
        onAuthed={() => {
          refreshAuth();
          go("/");
        }}
      />
    );
  }

  if (page === "login") {
    return (
      <Auth
        onAuthed={() => {
          refreshAuth();
          go("/settings/account");
        }}
      />
    );
  }


  return (
    <div className={page === "taste-lab" && !tasteHome ? "app is-taste" : "app"}>
      <aside className="sidebar">
        <div className="brand">Dinnerdesk</div>
        <nav className="side-nav">
          <NavLink href="/" navKey="plan" label="Plan" icon="plan" page={page} />
          <NavLink href="/recipes" navKey="recipes" label="Recipes" icon="recipes" page={page} />
          <NavLink href="/grocery" navKey="grocery" label="Grocery" icon="grocery" page={page} />
          <NavLink href="/prep" navKey="prep" label="Prep" icon="prep" page={page} />
          <NavLink href="/settings" navKey="settings" label="Settings" icon="settings" page={page} className="side-break" />
          <NavLink href="/kitchen" navKey="kitchen" label="My kitchen" icon="kitchen" page={page} />
        </nav>
      </aside>
      <div className="main" key={tabRootVersion}>
        {!authStatus.authenticated && !guestNoticeDismissed && <div className="guest-notice">Using a guest kitchen. Clearing browser data can lose access. <a href="/login">Sign in or create an account</a> to protect your data. <button type="button" onClick={() => setGuestNoticeDismissed(true)}>Dismiss</button></div>}
        {page === "plan" && <Plan />}
        {page === "recipes" && <Recipes />}
        {page === "recipe" && <Recipe id={route.id} />}
        {page === "new-recipe" && <NewRecipe />}
        {page === "grocery" && <Grocery />}
        {page === "prep" && <Prep />}
        {page === "kitchen" && <Kitchen view={route.view || "hub"} />}
        {page === "more" && <More />}
        {page === "settings" && <Settings />}
        {page === "account-security" && <AccountSecurity />}
        {page === "ingredient-review" && admin && <IngredientReview />}
        {page === "recipe-flags" && admin && <RecipeFlags />}
        {page === "taste-lab" && <TasteLab />}
        {page === "filters" && <Filters />}
        {page === "social" && <Social />}
        {page === "newsletter" && <Newsletter />}
      </div>
      <nav className="tabbar" aria-label="Primary">
        <NavLink href="/" navKey="plan" label="Plan" icon="plan" page={page} />
        <NavLink href="/recipes" navKey="recipes" label="Recipes" icon="recipes" page={page} />
        <NavLink href="/grocery" navKey="grocery" label="Grocery" icon="grocery" page={page} />
        <NavLink href="/prep" navKey="prep" label="Prep" icon="prep" page={page} className="optional-prep" />
        <NavLink href="/more" navKey="more-tab" label="More" icon="settings" page={page} />
      </nav>
      <Tour />
    </div>
  );
}
