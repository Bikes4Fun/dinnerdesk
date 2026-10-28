export function Icon({ name, size = 22 }) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: name === "plus" ? 2.25 : 1.75,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": true,
  };
  if (name === "trash") {
    return <svg {...common}><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" /></svg>;
  }
  if (name === "calendar") {
    return <svg {...common}><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M7 3v4M17 3v4M3 10h18" /></svg>;
  }
  if (name === "plan") {
    return (
      <svg {...common}>
        <rect x="3" y="3" width="7" height="7" rx="1.2" />
        <rect x="14" y="3" width="7" height="7" rx="1.2" />
        <rect x="3" y="14" width="7" height="7" rx="1.2" />
        <rect x="14" y="14" width="7" height="7" rx="1.2" />
      </svg>
    );
  }
  if (name === "recipes") {
    return (
      <svg {...common}>
        <path d="M4 7h16M4 12h16M4 17h10" />
      </svg>
    );
  }
  if (name === "grocery") {
    return (
      <svg {...common}>
        <path d="M3 4h2l2.2 11h11l2-8H6.2" />
        <circle cx="9" cy="19.5" r="1.3" />
        <circle cx="17" cy="19.5" r="1.3" />
      </svg>
    );
  }
  if (name === "prep") {
    return (
      <svg {...common}>
        <path d="M4 4l11 11M15 15l2.5 2.5a2 2 0 102.8-2.8L17.8 12.2" />
      </svg>
    );
  }
  if (name === "kitchen") {
    return (
      <svg {...common}>
        <path d="M6 21V8M18 21V8M4 8h16M8 4h8M4 21h16M10 13h4" />
      </svg>
    );
  }
  if (name === "pantry") {
    return (
      <svg {...common}>
        <path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1z" />
        <path d="M10 21v-6h4v6" />
      </svg>
    );
  }
  if (name === "print") {
    return (
      <svg {...common}>
        <path d="M6 9V3h12v6M6 17H4a1 1 0 0 1-1-1v-6a1 1 0 0 1 1-1h16a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1h-2" />
        <rect x="6" y="13" width="12" height="8" rx="1" />
      </svg>
    );
  }
  if (name === "admin") {
    return <svg {...common}><path d="M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6l7-3z" /></svg>;
  }
  if (name === "settings") {
    return (
      <svg {...common}>
        <circle cx="12" cy="12" r="3" />
        <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4" />
      </svg>
    );
  }
  if (name === "flag") {
    return (
      <svg {...common}>
        <path d="M5 21V4M5 4h11l-2 4 2 4H5" />
      </svg>
    );
  }
  if (name === "dots") {
    return (
      <svg {...common} fill="currentColor" stroke="none">
        <circle cx="5" cy="12" r="1.8" />
        <circle cx="12" cy="12" r="1.8" />
        <circle cx="19" cy="12" r="1.8" />
      </svg>
    );
  }
  if (name === "check") {
    return (
      <svg {...common} strokeWidth={3.2}>
        <path d="M5 12.5l4.5 4.5L19 7.5" />
      </svg>
    );
  }
  if (name === "close") {
    return (
      <svg {...common} strokeWidth={2.2}>
        <path d="M6 6l12 12M18 6L6 18" />
      </svg>
    );
  }
  if (name === "chevron-down") {
    return (
      <svg {...common}>
        <path d="M6 9l6 6 6-6" />
      </svg>
    );
  }
  if (name === "search") {
    return (
      <svg {...common}>
        <circle cx="11" cy="11" r="6.25" />
        <path d="M16 16.5 21 21.5" />
      </svg>
    );
  }
  if (name === "thumbs-up" || name === "thumbs-down") {
    const d = "M7 11v9H4a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1h3zm0 0l4-8c1.7 0 3 1.3 3 3v3h5.2a2 2 0 0 1 2 2.3l-1.2 7A2 2 0 0 1 18 20H7";
    return (
      <svg {...common} style={name === "thumbs-down" ? { transform: "rotate(180deg)" } : undefined}>
        <path d={d} />
      </svg>
    );
  }
  if (name === "about") {
    return (
      <svg {...common}>
        <circle cx="12" cy="12" r="8" />
        <path d="M12 11v5M12 8h.01" />
      </svg>
    );
  }
  if (name === "plus") {
    return (
      <svg {...common}>
        <path d="M12 5v14M5 12h14" />
      </svg>
    );
  }
  return (
    <svg {...common}>
      <circle cx="12" cy="12" r="8" />
    </svg>
  );
}
