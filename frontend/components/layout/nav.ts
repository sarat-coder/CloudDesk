export interface NavItem {
  label: string;
  href: string;
  icon: string;
  adminOnly?: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: "grid" },
  { label: "Tickets", href: "/tickets", icon: "inbox" },
  { label: "Customers", href: "/customers", icon: "users" },
  { label: "Knowledge", href: "/knowledge", icon: "book" },
  { label: "Escalations", href: "/escalations", icon: "alert-triangle" },
  { label: "Agents", href: "/agents", icon: "cpu" },
  { label: "Audit", href: "/audit", icon: "shield" },
  { label: "Settings", href: "/settings", icon: "settings", adminOnly: true },
];
