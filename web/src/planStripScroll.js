/** First load and switching weeks start at the beginning; additions to a shown week scroll. */
export function shouldScrollToNewMeal(previous, next) {
  return Boolean(previous && next && previous.id === next.id && previous.slots?.length > 0
    && next.slots?.length > previous.slots.length);
}

/** Reset a reused track on a new week, even if the new week has the same meal count. */
export function planStripScrollPosition(previous, next) {
  if (previous?.id !== next?.id) return "start";
  return shouldScrollToNewMeal(previous, next) ? "end" : null;
}
