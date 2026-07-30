/// Resultado tipado de CajaService.calcularCaja().
/// Todos los campos en COP como int. Zero Map dinámico.
class CajaResultado {
  final int openingBase;
  final int openingCarry;
  final int recaudoReal;
  final int reversales;
  final int gastos;
  final int ahorro;
  final int vales;
  final int entregas;
  final int recibidos;
  final int desembolsos;
  final int efectivoEsperado;
  final int pagosCount;
  final int reversalesCount;
  final int movimientosCount;

  const CajaResultado({
    required this.openingBase,
    required this.openingCarry,
    required this.recaudoReal,
    required this.reversales,
    required this.gastos,
    required this.ahorro,
    required this.vales,
    required this.entregas,
    required this.recibidos,
    required this.desembolsos,
    required this.efectivoEsperado,
    required this.pagosCount,
    required this.reversalesCount,
    required this.movimientosCount,
  });

  /// Fórmula canónica:
  /// efectivoEsperado = openingBase + openingCarry + recaudoReal
  ///   - reversales - gastos - ahorro - vales - entregas - desembolsos + recibidos
  int get calcularEfectivoEsperado =>
      openingBase + openingCarry + recaudoReal
      - reversales - gastos - ahorro - vales - entregas - desembolsos + recibidos;
}
