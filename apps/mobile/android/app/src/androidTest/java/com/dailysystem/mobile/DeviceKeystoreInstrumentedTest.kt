package com.dailysystem.mobile

import android.util.Base64
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.StandardMethodCodec
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import java.nio.ByteBuffer
import java.nio.charset.StandardCharsets

/**
 * Gate A (Bloque 7) — prueba Android instrumentada del motor de identidad.
 *
 * Criterios de salida de la auditoria de dispositivos (DAILY-SYSTEM-AUDITORIA):
 *   a) generacion de par EC P-256 en AndroidKeyStore
 *   b) clave privada NO exportable (AndroidKeyStore nunca expone el material)
 *   c) clave publica SPKI (X.509) exportable
 *   d) firma SHA256withECDSA verificable (challenge-response JCS)
 *   e) delete/rotate de alias
 *   f) MethodChannel productivo (D7-02) resolviendo generate/sign/verify
 *      con la clave NO exportable
 *
 * Corre en AVD API 35 (DailySystem_API35).
 */
@RunWith(AndroidJUnit4::class)
class DeviceKeystoreInstrumentedTest {

    private lateinit var identity: DeviceIdentityService
    private var engine: FlutterEngine? = null

    private val testAlias = "daily_system_test_instrumented"

    @Before
    fun setUp() {
        identity = DeviceIdentityService(alias = testAlias)
        identity.delete()
    }

    @After
    fun tearDown() {
        identity.delete()
        val e = engine
        if (e != null) {
            InstrumentationRegistry.getInstrumentation().runOnMainSync { e.destroy() }
        }
    }

    @Test
    fun test_01_genera_par_ec_p256_y_spki_publico_exportable() {
        val spki = identity.generateOrGetPublicKeySpki()
        assertTrue("debe generar un SPKI", spki.isNotBlank())

        val decoded = Base64.decode(spki, Base64.NO_WRAP)
        assertTrue("SPKI debe ser DER X.509", decoded[0] == 0x30.toByte())

        val pub = java.security.KeyFactory.getInstance("EC")
            .generatePublic(java.security.spec.X509EncodedKeySpec(decoded))
        assertTrue("debe ser clave EC", pub is java.security.interfaces.ECPublicKey)
        val ec = pub as java.security.interfaces.ECPublicKey
        assertEquals("curva P-256", 256, ec.params.curve.field.fieldSize)
    }

    @Test
    fun test_02_private_key_no_exportable_en_keystore() {
        identity.generateOrGetPublicKeySpki()
        assertFalse(
            "la privada del AndroidKeyStore nunca debe ser exportable",
            identity.isPrivateKeyExportable(),
        )
    }

    @Test
    fun test_03_spki_publico_recuperable_y_utilizable() {
        identity.generateOrGetPublicKeySpki()
        assertTrue("la publica debe ser utilizable", identity.hasUsableP256Key())
        assertTrue("SPKI debe ser recuperable", identity.getPublicKeySpki().isNotBlank())
    }

    @Test
    fun test_04_firma_sha256with_ecdsa_verificable() {
        identity.generateOrGetPublicKeySpki()
        val payload = "challenge-jcs-daily-auth-v1|a1b2c3d4".toByteArray(StandardCharsets.UTF_8)

        val firma = identity.sign(payload)
        assertNotNull(firma)
        assertTrue("firma base64url no vacia", firma.isNotBlank())

        assertTrue("firma debe verificar contra la publica", identity.verify(firma, payload))
        assertFalse(
            "payload alterado debe rechazarse",
            identity.verify(firma, "challenge-alterado".toByteArray()),
        )
        assertFalse(
            "firma corrupta debe rechazarse",
            identity.verify("firma_invalida", payload),
        )
    }

    @Test
    fun test_05_delete_invalida_alias_immediatamente() {
        identity.generateOrGetPublicKeySpki()
        assertTrue("delete debe reportar exito", identity.delete())
        assertFalse("tras delete no debe existir clave", identity.hasUsableP256Key())
        assertFalse("tras delete no debe poder firmarse", signatureFailsAfterDelete())
    }

    @Test
    fun test_06_rotate_genera_nueva_clave_usable() {
        identity.generateOrGetPublicKeySpki()
        val payload = "rotate-check".toByteArray(StandardCharsets.UTF_8)
        val firmaVieja = identity.sign(payload)

        val spkiNuevo = identity.rotate()
        assertTrue("rotate debe devolver un SPKI", spkiNuevo.isNotBlank())
        assertTrue("clave nueva debe ser utilizable", identity.hasUsableP256Key())

        val firmaNueva = identity.sign(payload)
        assertTrue("clave nueva firma y verifica", identity.verify(firmaNueva, payload))
        assertFalse(
            "firma con clave vieja debe rechazarse tras rotate",
            identity.verify(firmaVieja, payload),
        )
    }

    @Test
    fun test_07_method_channel_productivo_generate_sign_verify() {
        val engine = launchEngine()

        // generate via channel
        val gen = invokeNative(engine, "generate", null)
        assertNotNull("channel generate responde", gen)
        @Suppress("UNCHECKED_CAST")
        val spki = (gen as Map<String, Any>)["spki"] as String
        assertTrue("channel SPKI no vacio", spki.isNotBlank())

        // sign via channel
        val payload = "daily-auth-v1|deadbeef".toByteArray(StandardCharsets.UTF_8)
        val payloadB64 = Base64.encodeToString(
            payload, Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING,
        )
        val signRaw = invokeNative(engine, "sign", mapOf("payload" to payloadB64))
        assertNotNull("channel sign responde", signRaw)
        @Suppress("UNCHECKED_CAST")
        val firma = (signRaw as Map<String, Any>)["firma"] as String

        // verify via channel
        val verifyRaw = invokeNative(
            engine,
            "verify",
            mapOf("payload" to payloadB64, "firma" to firma),
        )
        assertNotNull("channel verify responde", verifyRaw)
        @Suppress("UNCHECKED_CAST")
        val valida = (verifyRaw as Map<String, Any>)["valida"] as Boolean
        assertTrue("channel verify acepta firma valida", valida)

        // delete + generate via channel (round-trip completo)
        val delRaw = invokeNative(engine, "delete", null)
        @Suppress("UNCHECKED_CAST")
        assertTrue("channel delete", (delRaw as Map<String, Any>)["borrado"] as Boolean)
        val regen = invokeNative(engine, "generate", null)
        assertNotNull("channel regenera tras delete", regen)
    }

    @Test
    fun test_08_method_channel_private_key_no_exportable() {
        val engine = launchEngine()
        invokeNative(engine, "generate", null)

        val raw = invokeNative(engine, "isPrivateKeyExportable", null)
        assertNotNull("channel exportable responde", raw)
        @Suppress("UNCHECKED_CAST")
        val exportable = (raw as Map<String, Any>)["exportable"] as Boolean
        assertFalse("privada no exportable via channel", exportable)
    }

    private fun launchEngine(): FlutterEngine {
        if (engine == null) {
            val ctx = InstrumentationRegistry.getInstrumentation().targetContext
            val instrumentation = InstrumentationRegistry.getInstrumentation()
            instrumentation.runOnMainSync {
                val e = FlutterEngine(ctx)
                MainActivity.registerDeviceIdentityChannel(e)
                engine = e
            }
        }
        return engine!!
    }

    private fun invokeNative(
        engine: FlutterEngine,
        method: String,
        args: Any?,
    ): Any? {
        val messenger = engine.dartExecutor.binaryMessenger

        // Accedemos al handler que MainActivity registro en el engine (D7-02).
        // El DartExecutor expone un DefaultBinaryMessenger que delega en el
        // DartMessenger interno; ahi vive el mapa de handlers. Como la API de
        // handlePlatformMessage fue removida en este embedding, lo recuperamos
        // por reflexion y lo invocamos con el MethodCall codificado.
        val handler = findRegisteredHandler(messenger)
            ?: throw AssertionError("handler del canal no registrado")

        val call = MethodCall(method, args)
        val encoded = StandardMethodCodec.INSTANCE.encodeMethodCall(call)
        encoded.rewind()

        var result: Any? = null
        var failure: Throwable? = null
        val done = java.util.concurrent.CountDownLatch(1)

        handler.onMessage(encoded) { reply: ByteBuffer? ->
            try {
                result = if (reply == null) {
                    null
                } else {
                    reply.rewind()
                    StandardMethodCodec.INSTANCE.decodeEnvelope(reply)
                }
            } catch (t: Throwable) {
                failure = t
            }
            done.countDown()
        }

        if (!awaitLatch(done)) {
            throw AssertionError("timeout invocando $method en el channel nativo")
        }
        if (failure != null) {
            throw AssertionError(
                "error en $method: class=${failure.javaClass.simpleName} msg=${failure.message} cause=${failure.cause}",
                failure,
            )
        }
        return result
    }

    @Suppress("UNCHECKED_CAST")
    private fun findRegisteredHandler(
        messenger: io.flutter.plugin.common.BinaryMessenger,
    ): io.flutter.plugin.common.BinaryMessenger.BinaryMessageHandler? {
        var current: Any = messenger
        var visited = 0
        while (visited++ < 4) {
            val messageHandlers = try {
                val f = current.javaClass.getDeclaredField("messageHandlers")
                f.isAccessible = true
                f.get(current) as? Map<String, Any>
            } catch (e: NoSuchFieldException) {
                null
            }
            if (messageHandlers != null) {
                val handlerInfo = messageHandlers[MainActivity.CHANNEL] ?: return null
                val handlerField = handlerInfo.javaClass.getDeclaredField("handler")
                handlerField.isAccessible = true
                return handlerField.get(handlerInfo)
                    as io.flutter.plugin.common.BinaryMessenger.BinaryMessageHandler
            }
            // Un nivel mas abajo (DefaultBinaryMessenger -> DartMessenger).
            val next = try {
                val f = current.javaClass.getDeclaredField("messenger")
                f.isAccessible = true
                f.get(current)
            } catch (e: NoSuchFieldException) {
                null
            }
            if (next == null) return null
            current = next
        }
        return null
    }

    private fun signatureFailsAfterDelete(): Boolean {
        return try {
            identity.sign("x".toByteArray())
            true
        } catch (e: Exception) {
            false
        }
    }

    private fun awaitAssert(block: () -> Unit) {
        var lastError: AssertionError? = null
        val deadline = System.currentTimeMillis() + 15_000
        while (System.currentTimeMillis() < deadline) {
            try {
                block()
                return
            } catch (e: AssertionError) {
                lastError = e
            }
            Thread.sleep(100)
        }
        throw lastError ?: AssertionError("timeout sin evaluacion")
    }

    private fun awaitLatch(latch: java.util.concurrent.CountDownLatch): Boolean =
        latch.await(15, java.util.concurrent.TimeUnit.SECONDS)
}
