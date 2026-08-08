package com.dailysystem.mobile

import android.util.Base64
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    companion object {
        const val CHANNEL = "daily_system/device_identity"

        /** Registra el canal D7-02 sobre un engine. Compartido con los tests. */
        fun registerDeviceIdentityChannel(flutterEngine: FlutterEngine) {
            val identity = DeviceIdentityService()
            MethodChannel(
                flutterEngine.dartExecutor.binaryMessenger,
                CHANNEL,
            ).setMethodCallHandler { call, result ->
                try {
                    when (call.method) {
                        "generate" -> {
                            val spki = identity.generateOrGetPublicKeySpki()
                            result.success(mapOf("spki" to spki))
                        }
                        "getPublicKeySpki" -> {
                            val spki = identity.getPublicKeySpki()
                            result.success(mapOf("spki" to spki))
                        }
                        "sign" -> {
                            val payloadB64 = call.argument<String>("payload")
                                ?: return@setMethodCallHandler result.error(
                                    "ARG_INVALIDO", "payload requerido", null
                                )
                            val payload = Base64.decode(
                                payloadB64,
                                Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING,
                            )
                            val firma = identity.sign(payload)
                            result.success(mapOf("firma" to firma))
                        }
                        "verify" -> {
                            val payloadB64 = call.argument<String>("payload")
                                ?: return@setMethodCallHandler result.error(
                                    "ARG_INVALIDO", "payload requerido", null
                                )
                            val firma = call.argument<String>("firma")
                                ?: return@setMethodCallHandler result.error(
                                    "ARG_INVALIDO", "firma requerida", null
                                )
                            val payload = Base64.decode(
                                payloadB64,
                                Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING,
                            )
                            result.success(mapOf("valida" to identity.verify(firma, payload)))
                        }
                        "delete" -> result.success(mapOf("borrado" to identity.delete()))
                        "rotate" -> {
                            val spki = identity.rotate()
                            result.success(mapOf("spki" to spki))
                        }
                        "isPrivateKeyExportable" ->
                            result.success(mapOf("exportable" to identity.isPrivateKeyExportable()))
                        else -> result.notImplemented()
                    }
                } catch (e: Exception) {
                    result.error("KEYSTORE_ERROR", e.message, null)
                }
            }
        }
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        registerDeviceIdentityChannel(flutterEngine)
    }
}
