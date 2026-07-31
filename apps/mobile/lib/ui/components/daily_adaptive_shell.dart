// ─── Daily Adaptive Shell ──────────────────────────────────────────
// Responsive navigation: BottomNavBar (compact) → NavigationRail (medium) → SideNav (expanded).

import 'package:flutter/material.dart';
import '../../theme/generated/daily_tokens.dart';

class DailyAdaptiveShell extends StatelessWidget {
  final int currentIndex;
  final ValueChanged<int> onIndexChange;
  final List<DailyNavItem> items;
  final Widget child;

  const DailyAdaptiveShell({
    super.key,
    required this.currentIndex,
    required this.onIndexChange,
    required this.items,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.of(context).size.width;

    if (width >= 840) {
      return _ExpandedShell(
        currentIndex: currentIndex,
        onIndexChange: onIndexChange,
        items: items,
        child: child,
      );
    } else if (width >= 600) {
      return _MediumShell(
        currentIndex: currentIndex,
        onIndexChange: onIndexChange,
        items: items,
        child: child,
      );
    } else {
      return _CompactShell(
        currentIndex: currentIndex,
        onIndexChange: onIndexChange,
        items: items,
        child: child,
      );
    }
  }
}

class DailyNavItem {
  final String label;
  final IconData icon;
  final IconData activeIcon;
  const DailyNavItem({
    required this.label,
    required this.icon,
    IconData? activeIcon,
  }) : activeIcon = activeIcon ?? icon;
}

// ── Compact: Bottom Navigation Bar ──
class _CompactShell extends StatelessWidget {
  final int currentIndex;
  final ValueChanged<int> onIndexChange;
  final List<DailyNavItem> items;
  final Widget child;

  const _CompactShell({
    required this.currentIndex,
    required this.onIndexChange,
    required this.items,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: child,
      bottomNavigationBar: NavigationBar(
        selectedIndex: currentIndex,
        onDestinationSelected: onIndexChange,
        backgroundColor: DailyTokens.surface,
        indicatorColor: DailyTokens.primaryContainer,
        destinations: items.map((item) => NavigationDestination(
          icon: Icon(item.icon, size: 24),
          selectedIcon: Icon(item.activeIcon, size: 24, color: DailyTokens.primary),
          label: item.label,
        )).toList(),
      ),
    );
  }
}

// ── Medium: Navigation Rail ──
class _MediumShell extends StatelessWidget {
  final int currentIndex;
  final ValueChanged<int> onIndexChange;
  final List<DailyNavItem> items;
  final Widget child;

  const _MediumShell({
    required this.currentIndex,
    required this.onIndexChange,
    required this.items,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Row(
        children: [
          NavigationRail(
            selectedIndex: currentIndex,
            onDestinationSelected: onIndexChange,
            labelType: NavigationRailLabelType.all,
            destinations: items.map((item) => NavigationRailDestination(
              icon: Icon(item.icon, size: 24),
              label: Text(item.label),
            )).toList(),
          ),
          const VerticalDivider(thickness: 1, width: 1),
          Expanded(child: child),
        ],
      ),
    );
  }
}

// ── Expanded: Side Navigation ──
class _ExpandedShell extends StatelessWidget {
  final int currentIndex;
  final ValueChanged<int> onIndexChange;
  final List<DailyNavItem> items;
  final Widget child;

  const _ExpandedShell({
    required this.currentIndex,
    required this.onIndexChange,
    required this.items,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Row(
        children: [
          NavigationRail(
            extended: true,
            selectedIndex: currentIndex,
            onDestinationSelected: onIndexChange,
            destinations: items.map((item) => NavigationRailDestination(
              icon: Icon(item.icon, size: 24),
              label: SizedBox(
                width: 120,
                child: Text(item.label, style: const TextStyle(fontSize: 13)),
              ),
            )).toList(),
          ),
          const VerticalDivider(thickness: 1, width: 1),
          Expanded(child: child),
        ],
      ),
    );
  }
}
