// ─── Daily Loading Skeleton ────────────────────────────────────────
// Skeleton loading that respects screen geometry.

import 'package:flutter/material.dart';
import '../../theme/generated/daily_tokens.dart';

class DailyLoadingSkeleton extends StatelessWidget {
  final double? width;
  final double? height;
  final bool circular;
  final double borderRadius;

  const DailyLoadingSkeleton({
    super.key,
    this.width,
    this.height,
    this.circular = false,
    this.borderRadius = DailyTokens.shapeSM,
  });

  @override
  Widget build(BuildContext context) {
    return AnimatedOpacity(
      opacity: 1.0,
      duration: const Duration(milliseconds: 200),
      child: Container(
        width: width,
        height: (height ?? 16) + (circular ? 8 : 0),
        decoration: BoxDecoration(
          color: DailyTokens.surfaceVariant,
          borderRadius: BorderRadius.circular(circular ? 12 : borderRadius),
        ),
      ),
    );
  }
}

/// Skeleton for a list of items
class DailyListSkeleton extends StatelessWidget {
  final int count;
  final double itemHeight;

  const DailyListSkeleton({
    super.key,
    this.count = 5,
    this.itemHeight = 80,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(DailyTokens.shapeMD),
      child: Column(
        children: List.generate(count, (i) => _skeletonItem()),
      ),
    );
  }

  Widget _skeletonItem() {
    return Padding(
      padding: const EdgeInsets.only(bottom: DailyTokens.shapeSM),
      child: Row(
        children: [
          DailyLoadingSkeleton(
            width: 48, height: 48,
            circular: true,
            borderRadius: 24,
          ),
          const SizedBox(width: DailyTokens.shapeMD),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                DailyLoadingSkeleton(width: double.infinity),
                const SizedBox(height: DailyTokens.spacingXS),
                DailyLoadingSkeleton(width: 100),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
