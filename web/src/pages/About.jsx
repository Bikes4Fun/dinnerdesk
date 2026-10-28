export function About() {
  return (
    <section className="screen">
      <header className="top">
        <h1>About</h1>
      </header>
      <div className="scroll pad privacy">
        <p>
          Dinnerdesk is a household meal planner. It suggests the week’s dinners, builds the grocery list from those meals, and lists the prep you can do ahead. The same kitchen works on the iPhone app and the website.
        </p>
        <p>
          It is built as one product on three surfaces: a SwiftUI iPhone app, a React website, and a Python API on PostgreSQL. A household shares one plan, grocery list, pantry, and preferences. Guests can use the app without an account; creating one keeps that kitchen.
        </p>

        <h2>Plan</h2>
        <p>
          This week is the plan. An empty week can start from a suggested plan or from meals you pick. A suggestion is a proposal: the current week and grocery list stay until you approve it. You can swap a meal, decline the set and see another, or fill only the open slots and keep what you already chose. Meals can be scheduled on a day, marked cooked, saved as a draft, or kept in history. Nothing is deleted when you start a new week.
        </p>

        <h2>Recipes</h2>
        <p>
          Recipes are always one tap away. Browse, search, favorite, mark To try, or hide a recipe you do not want suggested. Diet, allergy, and avoid filters apply in Recipes and in suggestions. Open a recipe for the ingredient list or Cook mode, with numbered steps and the amounts for each step. Edits stay with your kitchen; the shared catalog is unchanged, and you can restore the original.
        </p>

        <h2>Taste Lab</h2>
        <p>
          Taste Lab learns what this household will cook. Swipe meals you would make or pass on, or review suggested plans. A pass is not suggested again. Swipe history can change a like to a pass, or the other way. Filters here are the same filters as Settings.
        </p>

        <h2>Grocery</h2>
        <p>
          The grocery list is built from the plan: one line per ingredient, amounts combined, grouped by aisle, and filtered by store. Pantry items stay on the list and are marked as ones you have. Staples you never need to buy stay checked. Check items off while you shop, add a line that is not from a recipe, and share the list.
        </p>

        <h2>Prep</h2>
        <p>
          Weekend prep is the make-ahead work for this plan: chop, mix, and portion now, then cook fresh later. The same task across meals is one row. A ring and a bar for each section show what is done. Checking an item off removes it until you ask to see completed work.
        </p>

        <h2>My kitchen</h2>
        <p>
          My kitchen holds what the household already has and how it shops: pantry, staples that are always checked off, ingredient substitutions, stores and aisles, and how many people you cook for. A substitution renames the grocery line for this kitchen only.
        </p>

        <h2>Accounts</h2>
        <p>
          Sign in on the website or the iPhone app. An invite link adds someone to the same household. You can change your password, sign out everywhere, leave, or remove a member. Privacy includes a download of the household’s data. The Quick start tour explains the main screens and can be skipped or replayed.
        </p>
      </div>
    </section>
  );
}
