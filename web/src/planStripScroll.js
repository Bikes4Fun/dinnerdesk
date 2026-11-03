/** First load and switching weeks start at the beginning; additions to a shown week scroll. */
export function shouldScrollToNewMeal(previous, next) {
  return Boolean(previous && next && previous.id === next.id && previous.slots?.length > 0
    && next.slots?.length > previous.slots.length);
}
