import 'package:flutter_test/flutter_test.dart';

import 'helpers/fixture.dart';

void main() {
  setUpAll(() {
    initTestDatabase();
  });

  test('fixture creates seeded DB with open jornada', () async {
    final f = await crearFixture();
    expect(f.cobradorId, isNotEmpty);
    expect(f.cobradorNombre, isNotEmpty);
    expect(f.negocioId, isNotEmpty);
    expect(f.rutaId, isNotEmpty);
    expect(f.rutaNombre, isNotEmpty);
    expect(f.creditoId, isNotEmpty);
    expect(f.jornada.isOpen, isTrue);
    expect(f.jornada.openingBase, kFixtureOpeningBase);
  });
}
