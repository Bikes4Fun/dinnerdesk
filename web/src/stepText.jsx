const BULLET = /^\s*(?:[-*•])\s+(.+)/;
const NUMBERED = /^\s*\d+[.)]\s+(.+)/;

function explodeInline(line) {
  const parts = line.split(/\s+-\s+/);
  if (parts.length < 2) return null;
  const intro = parts[0].trim();
  const items = parts.slice(1).map((x) => x.trim()).filter(Boolean);
  if (!items.length) return null;
  if (/:\s*$/.test(intro) || items.length >= 2) return { intro, items };
  return null;
}

function headingSplit(text) {
  const lines = text.split("\n");
  const first = lines[0];
  if (first.includes("://")) return null;
  const m = first.match(/^([^:]{1,70}:)\s+(\S.*)$/);
  if (!m) return null;
  const rest = [m[2], ...lines.slice(1)].filter(Boolean).join("\n");
  return { label: m[1], rest };
}

export function amountLines(text) {
  const lines = String(text || "")
    .replace(/\r\n/g, "\n")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  if (!lines.length) return "";
  const marked = lines.every((line) => BULLET.test(line) || NUMBERED.test(line));
  return marked ? lines.join("\n") : lines.map((line) => `- ${line}`).join("\n");
}

export function parseStepBlocks(text) {
  const lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
  const blocks = [];
  let para = [];
  let list = [];
  let ordered = false;

  function flushList() {
    if (!list.length) return;
    blocks.push({ type: ordered ? "ol" : "ul", items: list });
    list = [];
    ordered = false;
  }

  function pushPara(text, label) {
    if (!text.trim()) return;
    if (!label) {
      const split = headingSplit(text);
      if (split) {
        blocks.push({ type: "p", text: split.label, label: true });
        if (split.rest.trim()) blocks.push({ type: "p", text: split.rest, label: false });
        return;
      }
    }
    blocks.push({ type: "p", text, label: !!label });
  }

  function flushPara() {
    if (!para.length) return;
    const pending = [];
    for (const line of para) {
      const exploded = explodeInline(line);
      if (exploded) {
        if (pending.length) {
          pushPara(pending.join("\n"), false);
          pending.length = 0;
        }
        const label = /:\s*$/.test(exploded.intro) && exploded.intro.length < 80;
        pushPara(exploded.intro, label);
        blocks.push({ type: "ul", items: exploded.items });
      } else {
        pending.push(line);
      }
    }
    if (pending.length) {
      const text = pending.join("\n");
      const label = pending.length === 1 && /:\s*$/.test(pending[0].trim()) && pending[0].trim().length < 80;
      pushPara(text, label);
    }
    para = [];
  }

  for (const line of lines) {
    const bullet = line.match(BULLET);
    const numbered = line.match(NUMBERED);
    if (bullet) {
      flushPara();
      if (list.length && ordered) flushList();
      ordered = false;
      list.push(bullet[1]);
      continue;
    }
    if (numbered) {
      flushPara();
      if (list.length && !ordered) flushList();
      ordered = true;
      list.push(numbered[1]);
      continue;
    }
    if (!line.trim()) {
      flushPara();
      flushList();
      continue;
    }
    flushList();
    para.push(line);
  }
  flushPara();
  flushList();
  return blocks;
}

function Inline({ text }) {
  const parts = [];
  const re = /\*\*(.+?)\*\*/g;
  let last = 0;
  let m;
  let i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    parts.push(<strong key={i}>{m[1]}</strong>);
    i += 1;
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

function Para({ text, label }) {
  const lines = text.split("\n");
  return (
    <p className={label ? "step-label" : undefined}>
      {lines.map((line, i) => (
        <span key={i}>
          {i > 0 ? <br /> : null}
          <Inline text={line} />
        </span>
      ))}
    </p>
  );
}

export function StepText({ text }) {
  const blocks = parseStepBlocks(text);
  if (!blocks.length) return null;
  return (
    <div className="step-body">
      {blocks.map((b, i) => {
        if (b.type === "p") return <Para key={i} text={b.text} label={b.label} />;
        const List = b.type === "ol" ? "ol" : "ul";
        return (
          <List key={i}>
            {b.items.map((item, j) => (
              <li key={j}>
                <Inline text={item} />
              </li>
            ))}
          </List>
        );
      })}
    </div>
  );
}
