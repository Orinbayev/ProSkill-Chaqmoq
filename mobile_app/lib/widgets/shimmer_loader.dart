import 'package:chaqmoq_mobile/core/theme/app_colors.dart';
import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/widgets/glass_card.dart';
import 'package:flutter/material.dart';
import 'package:shimmer/shimmer.dart';

class ShimmerLoader extends StatelessWidget {
  const ShimmerLoader.list({
    super.key,
    this.itemCount = 6,
  }) : _variant = _ShimmerVariant.list;

  const ShimmerLoader.grid({
    super.key,
    this.itemCount = 4,
  }) : _variant = _ShimmerVariant.grid;

  final int itemCount;
  final _ShimmerVariant _variant;

  @override
  Widget build(BuildContext context) {
    return Shimmer.fromColors(
      baseColor: AppColors.surface,
      highlightColor: AppColors.surfaceAlt,
      child: _variant == _ShimmerVariant.grid ? _buildGrid() : _buildList(),
    );
  }

  Widget _buildList() {
    return ListView.separated(
      physics: const NeverScrollableScrollPhysics(),
      shrinkWrap: true,
      itemCount: itemCount,
      separatorBuilder: (context, index) => const SizedBox(height: AppSpacing.lg),
      itemBuilder: (context, index) {
        return const GlassCard(
          child: SizedBox(height: 84),
        );
      },
    );
  }

  Widget _buildGrid() {
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: itemCount,
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        crossAxisSpacing: AppSpacing.lg,
        mainAxisSpacing: AppSpacing.lg,
        childAspectRatio: 1.3,
      ),
      itemBuilder: (context, index) => const GlassCard(
        child: SizedBox.expand(),
      ),
    );
  }
}

enum _ShimmerVariant { list, grid }
