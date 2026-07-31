// ─── Daily Confirm Sheet ───────────────────────────────────────────
// Bottom sheet modal for confirmation dialogs.

import 'package:flutter/material.dart';
import '../../theme/generated/daily_tokens.dart';
import 'daily_primary_button.dart';
import 'daily_secondary_button.dart';

class DailyConfirmSheet extends StatelessWidget {
  final String title;
  final String message;
  final String confirmLabel;
  final String cancelLabel;
  final VoidCallback onConfirm;
  final Color? confirmColor;
  final String? warningText;

  const DailyConfirmSheet({
    super.key,
    required this.title,
    required this.message,
    required this.confirmLabel,
    this.cancelLabel = 'Cancelar',
    required this.onConfirm,
    this.confirmColor,
    this.warningText,
  });

  @override
  Widget build(BuildContext context) {
    return SliverPersistentHeader(
      delegate: _ConfirmSheetDelegate(
        title: title,
        message: message,
        confirmLabel: confirmLabel,
        cancelLabel: cancelLabel,
        onConfirm: onConfirm,
        confirmColor: confirmColor,
        warningText: warningText,
      ),
      pinned: true,
    );
  }
}

class _ConfirmSheetDelegate extends SliverPersistentHeaderDelegate {
  final String title;
  final String message;
  final String confirmLabel;
  final String cancelLabel;
  final VoidCallback onConfirm;
  final Color? confirmColor;
  final String? warningText;

  _ConfirmSheetDelegate({
    required this.title,
    required this.message,
    required this.confirmLabel,
    required this.cancelLabel,
    required this.onConfirm,
    this.confirmColor,
    this.warningText,
  });

  @override
  Widget build(BuildContext context, double shrinkOffset, bool overlapsContent) {
    return Container(
      decoration: BoxDecoration(
        color: DailyTokens.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(DailyTokens.shapeXL)),
      ),
      child: Padding(
        padding: EdgeInsets.only(
          top: DailyTokens.shapeMD,
          bottom: MediaQuery.of(context).viewInsets.bottom,
          left: DailyTokens.shapeLG,
          right: DailyTokens.shapeLG,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: const TextStyle(
                fontSize: 20, fontWeight: FontWeight.w700,
                color: DailyTokens.textPrimary,
              ),
            ),
            const SizedBox(height: DailyTokens.shapeSM),
            Text(
              message,
              style: const TextStyle(fontSize: 14, color: DailyTokens.textSecondary),
            ),
            if (warningText != null) ...[
              const SizedBox(height: DailyTokens.shapeSM),
              Container(
                padding: const EdgeInsets.all(DailyTokens.shapeSM),
                decoration: BoxDecoration(
                  color: DailyTokens.warning.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(DailyTokens.shapeSM),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.warning_amber_rounded, size: 18, color: DailyTokens.warning),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        warningText!,
                        style: const TextStyle(fontSize: 12, color: DailyTokens.warning),
                      ),
                    ),
                  ],
                ),
              ),
            ],
            const SizedBox(height: DailyTokens.shapeLG),
            DailyPrimaryButton(
              label: confirmLabel,
              onPressed: onConfirm,
              color: confirmColor,
            ),
            const SizedBox(height: DailyTokens.shapeSM),
            DailySecondaryButton(
              label: cancelLabel,
              onPressed: () => Navigator.of(context).pop(),
            ),
          ],
        ),
      ),
    );
  }

  @override
  double get maxExtent => 320;
  @override
  double get minExtent => 200;
  @override
  bool shouldRebuild(covariant SliverPersistentHeaderDelegate old) => true;
}
