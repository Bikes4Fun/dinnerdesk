import table from "../../ios/dinnerdesk/copy.json";

/** Shared wording, using the same key and placeholder contract as the native Copy adapters. */
export class Copy {
  static text(id) {
    const value = table[id];
    if (typeof value !== "string") throw new Error(`Missing copy key: ${id}`);
    return value.replaceAll("{app}", table["app.name"]);
  }

  static steps(prefix, count) {
    return Array.from({ length: count }, (_, index) => {
      const key = `${prefix}.${index + 1}`;
      return { title: this.text(`${key}.title`), body: this.text(key) };
    });
  }
}
