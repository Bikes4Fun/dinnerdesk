import { Copy } from "./Copy.js";
import { useEffect, useRef, useState } from "react";
import FoodPhoto from "./FoodPhoto.jsx";
import { RecipeStatusLine } from "./ReviewedBadge.jsx";
import { go } from "./nav.js";

/**
 * Shared RecipeTile template — not wired to screens yet.
 *
 * Future callers: Plan list/grid, Recipes browse, My Recipes, suggested plan, swap,
 * Taste Lab (larger + swipe wrapper), Hidden, plan strip, grocery “used in” rows.
 *
 * Structure:
 *  1. Photo (* square crop, shared corner radius; options: size, opacity, open-on-tap)
 *  2. Overlays via RecipeTilePhotoOverlay (* standard circle; options: shown, where,
 *     interactive vs static; content inside the circle)
 *  3. Body = name (* default typography) + meta (view under|beside; named content types)
 *  4. Context menu (option): right-click / long-press on mobile web
 *
 * * = always-on default. Without * = page option.
 * REVIEW: defaults — cook time + kitchen-tested meta on with reserved height; servings off;
 *         no overlays / no context menu until a page opts in.
 * REVIEW: kitchen-tested as photo badge vs body meta — both supported.
 * Copy: feature name stays "To try" (not "To Try").
 *
 * Leave cards.jsx wired until migrate.
 */

export const RecipeTileCorner = {
  topLeading: "top-leading",
  topTrailing: "top-trailing",
  bottomLeading: "bottom-leading",
  bottomTrailing: "bottom-trailing",
  center: "center",
};

/** Universal overlay chrome: * standard-size circle + hit target. */
export function RecipeTilePhotoOverlay({
  corner = RecipeTileCorner.topTrailing,
  mode = "interactive",
  label,
  onClick,
  children,
  className = "",
}) {
  const Tag = mode === "interactive" ? "button" : "span";
  return (
    <Tag
      type={mode === "interactive" ? "button" : undefined}
      className={`recipe-tile-overlay recipe-tile-overlay--${corner}${className ? ` ${className}` : ""}${mode === "static" ? " is-static" : ""}`}
      aria-label={label}
      onClick={
        mode === "interactive"
          ? (e) => {
              e.stopPropagation();
              onClick?.(e);
            }
          : undefined
      }
    >
      <span className="recipe-tile-overlay-chrome">{children}</span>
    </Tag>
  );
}

export function RecipeTileAddButton({ onPlan, onClick, corner = RecipeTileCorner.topTrailing }) {
  return (
    <RecipeTilePhotoOverlay
      corner={corner}
      mode="interactive"
      label={onPlan ? Copy.text("ui.remove.from.this.plan") : Copy.text("ui.add.to.this.plan")}
      onClick={onClick}
      className={onPlan ? "is-on" : ""}
    >
      {onPlan ? "✓" : "+"}
    </RecipeTilePhotoOverlay>
  );
}

export function RecipeTileHeartButton({ on, onClick, corner = RecipeTileCorner.topLeading }) {
  return (
    <RecipeTilePhotoOverlay
      corner={corner}
      mode="interactive"
      label={on ? Copy.text("ui.remove.from.your.favorites") : Copy.text("ui.save.to.your.favorites")}
      onClick={onClick}
      className={on ? "is-on is-heart" : "is-heart"}
    >
      {on ? "♥" : "♡"}
    </RecipeTilePhotoOverlay>
  );
}

export function RecipeTileSwapButton({ onClick, disabled, corner = RecipeTileCorner.topTrailing }) {
  return (
    <RecipeTilePhotoOverlay
      corner={corner}
      mode="interactive"
      label={Copy.text("ui.swap.meal")}
      onClick={disabled ? undefined : onClick}
      className={disabled ? "is-disabled" : ""}
    >
      ↻
    </RecipeTilePhotoOverlay>
  );
}

export function RecipeTileSaveForLaterButton({ on, onClick, corner = RecipeTileCorner.topLeading }) {
  return (
    <RecipeTilePhotoOverlay
      corner={corner}
      mode="interactive"
      label={on ? Copy.text("ui.remove.from.to.try") : Copy.text("ui.save.to.to.try")}
      onClick={onClick}
      className={on ? "is-on" : ""}
    >
      {on ? "★" : "☆"}
    </RecipeTilePhotoOverlay>
  );
}

export function RecipeTileCookedButton({ on, onClick, corner = RecipeTileCorner.topTrailing }) {
  return (
    <RecipeTilePhotoOverlay
      corner={corner}
      mode="interactive"
      label={on ? Copy.text("ui.mark.as.not.cooked") : Copy.text("ui.mark.as.cooked")}
      onClick={onClick}
      className={on ? "is-on" : ""}
    >
      {on ? "✓" : "○"}
    </RecipeTilePhotoOverlay>
  );
}

export function RecipeTileFlagButton({ onClick, corner = RecipeTileCorner.topTrailing }) {
  return (
    <RecipeTilePhotoOverlay corner={corner} mode="interactive" label={Copy.text("ui.report.photo")} onClick={onClick}>
      ⚑
    </RecipeTilePhotoOverlay>
  );
}

export function RecipeTileKitchenTestedBadge({ corner = RecipeTileCorner.topLeading }) {
  return (
    <RecipeTilePhotoOverlay corner={corner} mode="static" label={Copy.text("recipe.reviewed.description")}>
      ✓
    </RecipeTilePhotoOverlay>
  );
}

export function RecipeTileComingSoonBadge() {
  return <span className="recipe-tile-coming-soon">{Copy.text("ui.coming.soon")}</span>;
}

/** Future tag e.g. "Low carb" — static; same overlay chrome. */
export function RecipeTileTagBadge({ label, corner = RecipeTileCorner.bottomLeading }) {
  return (
    <RecipeTilePhotoOverlay corner={corner} mode="static" label={label} className="is-tag">
      {label}
    </RecipeTilePhotoOverlay>
  );
}

/**
 * Standard context-menu item factories. Page can also pass extras: { id, title, action, destructive? }.
 * Copy: "To try" not "To Try".
 */
export const RecipeTileMenuItem = {
  favorite: (on, action) => ({ id: "favorite", title: on ? "Unfavorite" : "Favorite", action }),
  plan: (on, action) => ({ id: "plan", title: on ? Copy.text("ui.remove.from.plan") : Copy.text("ui.add.to.plan"), action }),
  toTry: (on, action) => ({ id: "toTry", title: on ? Copy.text("ui.remove.from.to.try") : Copy.text("ui.to.try.2"), action }),
  hide: (on, action) => ({
    id: "hide",
    title: on ? Copy.text("ui.unhide.recipe") : Copy.text("ui.hide.recipe"),
    destructive: !on,
    action,
  }),
  cooked: (on, action) => ({
    id: "cooked",
    title: on ? Copy.text("ui.mark.as.not.cooked") : Copy.text("ui.mark.as.cooked"),
    action,
  }),
  extra: (id, title, action, opts = {}) => ({ id, title, action, ...opts }),
};

/**
 * @param {object} props
 * @param {'under'|'beside'} [props.metaPlacement='under']
 * @param {boolean} [props.showCookTime=true] — reserved height when opted in
 * @param {boolean} [props.showKitchenTested=true]
 * @param {boolean} [props.showServings=false]
 * @param {boolean} [props.showYourSelection=false]
 * @param {boolean} [props.showSchedule=false]
 * @param {Array} [props.menuItems=[]] — empty = no context menu
 * @param {React.ReactNode} [props.overlays] — photo overlay buttons/badges
 */
export function RecipeTile({
  name,
  photoPath,
  photoSide,
  photoOpacity = 1,
  comingSoon = false,
  openEnabled = true,
  recipeId,
  minutes,
  reviewed = false,
  servings,
  yourSelection = false,
  scheduleLabel,
  metaPlacement = "under",
  showCookTime = true,
  showKitchenTested = true,
  showServings = false,
  showYourSelection = false,
  showSchedule = false,
  menuItems = [],
  overlays = null,
  onOpen,
  className = "",
}) {
  const canOpen = openEnabled && !comingSoon;
  const [menu, setMenu] = useState(null);
  const menuRef = useRef(null);
  // Beside defaults to a swap-picker-sized thumb when photoSide is omitted.
  const side = photoSide ?? (metaPlacement === "beside" ? 70 : undefined);

  const href = canOpen && onOpen == null && recipeId != null ? `/recipes/${recipeId}` : null;

  function open(e) {
    if (!canOpen) return;
    if (onOpen) {
      onOpen();
      return;
    }
    if (recipeId != null) {
      e?.preventDefault();
      go(`/recipes/${recipeId}`);
    }
  }

  function onContextMenu(e) {
    if (!menuItems.length) return;
    e.preventDefault();
    setMenu({ x: e.clientX, y: e.clientY });
  }

  useEffect(() => {
    if (!menu) return undefined;
    function close(e) {
      if (menuRef.current && menuRef.current.contains(e.target)) return;
      setMenu(null);
    }
    function onKey(e) {
      if (e.key === "Escape") setMenu(null);
    }
    window.addEventListener("mousedown", close);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", close);
      window.removeEventListener("keydown", onKey);
    };
  }, [menu]);

  const statusRecipe = {
    cooking_minutes: showCookTime ? minutes : null,
    reviewed: showKitchenTested && reviewed,
  };
  const statusVisible =
    (showCookTime && minutes > 0) || (showKitchenTested && reviewed);

  const meta = (
    <div className="recipe-tile-meta">
      {(showCookTime || showKitchenTested) && (
        <div
          className="recipe-tile-meta-status"
          style={{ opacity: statusVisible ? 1 : 0 }}
          aria-hidden={!statusVisible}
        >
          <RecipeStatusLine recipe={statusRecipe} />
        </div>
      )}
      {showServings && (
        <p className="recipe-tile-meta-line" style={{ opacity: servings != null ? 1 : 0 }}>
          {servings != null ? `${servings} servings` : "0 servings"}
        </p>
      )}
      {showYourSelection && (
        <p className="recipe-tile-meta-line" style={{ opacity: yourSelection ? 1 : 0 }} aria-hidden={!yourSelection}>
          Your selection
        </p>
      )}
      {showSchedule && (
        <p
          className="recipe-tile-meta-line"
          style={{ opacity: scheduleLabel ? 1 : 0 }}
          aria-hidden={!scheduleLabel}
        >
          {scheduleLabel || "Schedule"}
        </p>
      )}
    </div>
  );

  const nameEl = (
    <p className={`recipe-tile-name${comingSoon ? " is-soon" : ""}`}>{name}</p>
  );

  const photoStyle = {
    ...(side ? { width: side, height: side } : null),
    opacity: comingSoon ? Math.min(photoOpacity, 0.6) : photoOpacity,
  };

  // Photo shell is a div (not a button) so overlay buttons are not nested inside another button.
  const photo = (
    <div className={`recipe-tile-photo${comingSoon ? " is-soon" : ""}`} style={photoStyle}>
      {canOpen ? (
        href ? (
          <a href={href} className="recipe-tile-photo-hit" onClick={open} aria-label={name} />
        ) : (
          <button type="button" className="recipe-tile-photo-hit" onClick={open} aria-label={name} />
        )
      ) : null}
      <FoodPhoto path={photoPath} />
      {comingSoon && <RecipeTileComingSoonBadge />}
      {overlays}
    </div>
  );

  return (
    <div
      className={`recipe-tile recipe-tile--${metaPlacement}${className ? ` ${className}` : ""}${comingSoon ? " is-coming-soon" : ""}`}
      onContextMenu={onContextMenu}
    >
      {photo}
      <div className="recipe-tile-body">
        {canOpen ? (
          href ? (
            <a href={href} className="recipe-tile-open" onClick={open}>
              {nameEl}
              {meta}
            </a>
          ) : (
            <button type="button" className="recipe-tile-open" onClick={open}>
              {nameEl}
              {meta}
            </button>
          )
        ) : (
          <>
            {nameEl}
            {meta}
          </>
        )}
      </div>
      {menu && menuItems.length > 0 && (
        <div
          ref={menuRef}
          className="recipe-tile-menu"
          role="menu"
          style={{ left: menu.x, top: menu.y }}
        >
          {menuItems.map((item) => (
            <button
              key={item.id}
              type="button"
              role="menuitem"
              className={`recipe-tile-menu-item${item.destructive ? " is-danger" : ""}`}
              onClick={() => {
                setMenu(null);
                item.action?.();
              }}
            >
              {item.title}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
