import React from 'react';
import {
  Target, Settings, Lock, CircleDot, ShoppingBag, FileText, BarChart3, Bot, Building2, Folder, Clock,
  Diamond, Search, Download, GitBranch, Globe, MessageSquare, ClipboardList, Activity, Zap, Brain,
  NotebookPen, Mail, Key, Lightbulb, Shuffle, Coins, Package, Star, Link, Users, CircleCheck, Hourglass,
  Play, Square, TriangleAlert, Rocket, Shield, Sparkles, Plug, PartyPopper, Server, Monitor, Volume2,
  Mic, Bug, Map, Microscope, Pencil, Smartphone, ShoppingCart, Eye, TrendingUp, Calendar, DoorOpen,
  Landmark, User, CircleHelp, Cloud, Moon, Plane, Tag, Image, GraduationCap, CreditCard, Receipt,
  Database, Repeat, Send, Clapperboard, Phone, Radio, Briefcase, X, Check, Command,
} from 'lucide-react';

/**
 * Glyph — renders the drawn icon for a legacy emoji/symbol "icon" string.
 *
 * Many screens and API payloads still describe icons as emoji ('🔒', '◎').
 * Emoji render differently on every platform and read as decoration, so they
 * are mapped onto the one stroke icon set here. Status dots become a filled
 * circle in the current colour. Anything unmapped (plain text, initials)
 * renders as-is, so an unknown value never disappears.
 */
const MAP = {
  '◎': Target, '⚙': Settings, '🔒': Lock, '🔐': Lock, '◉': CircleDot, '🛍': ShoppingBag, '🛒': ShoppingCart,
  '📄': FileText, '📊': BarChart3, '📈': TrendingUp, '🤖': Bot, '🏢': Building2, '🏛': Landmark, '📁': Folder,
  '🗄': Database, '⏱': Clock, '◈': Diamond, '✦': Sparkles, '🔍': Search, '🔎': Search, '⬇': Download,
  '⎇': GitBranch, '🌐': Globe, '💬': MessageSquare, '📋': ClipboardList, '🏃': Activity, '⚡': Zap,
  '🧠': Brain, '📝': NotebookPen, '✎': Pencil, '✉': Mail, '📨': Send, '🔑': Key, '💡': Lightbulb,
  '🔀': Shuffle, '🔁': Repeat, '💰': Coins, '📦': Package, '★': Star, '⭐': Star, '🎯': Target, '🔗': Link,
  '👥': Users, '👤': User, '🧑': User, '✅': CircleCheck, '⏳': Hourglass, '▶': Play, '⏹': Square,
  '⚠': TriangleAlert, '🚀': Rocket, '🛡': Shield, '🔌': Plug, '🎉': PartyPopper, '🖥': Monitor,
  '🔊': Volume2, '🔈': Volume2, '🎙': Mic, '🎤': Mic, '🐞': Bug, '🗺': Map, '🔬': Microscope, '📱': Smartphone,
  '👁': Eye, '📅': Calendar, '🚪': DoorOpen, '❓': CircleHelp, '☁': Cloud, '☽': Moon, '✈': Plane,
  '🏷': Tag, '🖼': Image, '🎓': GraduationCap, '💳': CreditCard, '🧾': Receipt, '🎬': Clapperboard,
  '📞': Phone, '📡': Radio, '💼': Briefcase, '🔮': Sparkles, '🦙': Bot, '🤗': Bot, '❌': X, '✗': X,
  '✕': X, '✓': Check, '⌘': Command, '🟦': Square,
};
const DOTS = { '🟢': 'var(--success)', '🟡': 'var(--warning)', '🔴': 'var(--danger)', '🔵': 'var(--accent)' };

export default function Glyph({ g, size = '1.05em', style }) {
  if (g == null || g === '') return null;
  const key = String(g).replace(/️/g, '').trim();
  if (DOTS[key]) {
    return <span aria-hidden="true" style={{ display: 'inline-block', width: '0.6em', height: '0.6em', borderRadius: '50%', background: DOTS[key], ...style }} />;
  }
  const C = MAP[key];
  if (!C) return <span aria-hidden="true" style={style}>{g}</span>;
  return <C size={size} strokeWidth={1.75} aria-hidden="true" focusable="false" style={{ flexShrink: 0, verticalAlign: '-0.15em', ...style }} />;
}

export { Glyph };
