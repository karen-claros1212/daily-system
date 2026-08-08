package com.dailysystem.mobile

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyPairGenerator
import java.security.KeyFactory
import java.security.KeyStore
import java.security.KeyStoreException
import java.security.Signature
import java.security.spec.ECGenParameterSpec
import java.security.spec.X509EncodedKeySpec

/**
 * Motor de identidad criptografica del dispositivo (D7-02, Bloque 7).
 *
 * Implementacion productiva via Android Keystore:
 *   - Par EC P-256 (secp256r1) NO exportable (KeyGenParameterSpec sin
 *     extractable; el propio Keystore nunca expone la privada).
 *   - Clave publica SPKI (SubjectPublicKeyInfo X.509) exportable.
 *   - Firma SHA256withECDSA sobre bytes exactos (para el challenge-response
 *     JCS daily-auth-v1 / daily-v1).
 *   - delete/rotate de alias (invalida la clave de forma inmediata).
 *
 * El alias se parametriza para permitir aislar pruebas instrumentadas sin
 * tocar la identidad real de la app.
 */
class DeviceIdentityService(
    private val alias: String = "daily_system_identity",
) {
    companion object {
        private const val ANDROID_KEYSTORE = "AndroidKeyStore"
        private const val KEY_ALGORITHM = KeyProperties.KEY_ALGORITHM_EC
        private const val CURVE = "secp256r1"
        private const val SIGNATURE_ALGORITHM = "SHA256withECDSA"
        private const val PURPOSE_SIGN_VERIFY =
            KeyProperties.PURPOSE_SIGN or KeyProperties.PURPOSE_VERIFY
        private const val DIGEST_SHA256 = KeyProperties.DIGEST_SHA256

        fun base64UrlNoPad(bytes: ByteArray): String =
            Base64.encodeToString(bytes, Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING)
    }

    private fun keyStore(): KeyStore {
        val ks = KeyStore.getInstance(ANDROID_KEYSTORE)
        ks.load(null)
        return ks
    }

    private fun hasAlias(): Boolean {
        try {
            return keyStore().containsAlias(alias)
        } catch (e: Exception) {
            return false
        }
    }

    /** Crea la clave si no existe. Devuelve el SPKI base64 de la publica. */
    fun generateOrGetPublicKeySpki(): String {
        if (!hasAlias()) {
            val generator = KeyPairGenerator.getInstance(KEY_ALGORITHM, ANDROID_KEYSTORE)
            val spec = KeyGenParameterSpec.Builder(alias, PURPOSE_SIGN_VERIFY)
                .setAlgorithmParameterSpec(ECGenParameterSpec(CURVE))
                .setDigests(DIGEST_SHA256)
                .build()
            generator.initialize(spec)
            generator.generateKeyPair()
        }
        return getPublicKeySpki()
    }

    /** SPKI (DER base64) de la clave publica del alias actual. */
    fun getPublicKeySpki(): String {
        val key = getPublicKeyOrNull()
            ?: throw IllegalStateException("no hay clave para el alias $alias")
        return Base64.encodeToString(key, Base64.NO_WRAP)
    }

    private fun getPublicKeyOrNull(): ByteArray? {
        val ks = keyStore()
        if (!ks.containsAlias(alias)) return null
        val entry = ks.getEntry(alias, null) as? KeyStore.PrivateKeyEntry ?: return null
        val cert = entry.certificate ?: return null
        return cert.publicKey.encoded
    }

    /** True si el alias existe y su publica es un SPKI EC P-256 valido. */
    fun hasUsableP256Key(): Boolean {
        val spki = getPublicKeyOrNull() ?: return false
        return try {
            val pub = parseSpki(spki)
            pub is java.security.interfaces.ECPublicKey &&
                pub.params.curve.field.fieldSize == 256
        } catch (e: Exception) {
            false
        }
    }

    private fun parseSpki(spki: ByteArray): java.security.PublicKey {
        val keySpec = X509EncodedKeySpec(spki)
        return KeyFactory.getInstance("EC").generatePublic(keySpec)
    }

    /**
     * Verifica si la clave privada es exportable. En Android Keystore la
     * privada nunca expone su material: getEncoded() == null / getFormat() == null.
     */
    fun isPrivateKeyExportable(): Boolean {
        val ks = keyStore()
        if (!ks.containsAlias(alias)) return false
        val entry = ks.getEntry(alias, null) as? KeyStore.PrivateKeyEntry ?: return false
        val priv = entry.privateKey
        // Claves del Keystore sin material exportable devuelven null aqui.
        return priv.format != null && priv.encoded != null
    }

    /**
     * Firma el payload (bytes exactos) con SHA256withECDSA y devuelve la
     * firma en base64url sin padding.
     */
    fun sign(payload: ByteArray): String {
        val ks = keyStore()
        if (!ks.containsAlias(alias)) {
            throw IllegalStateException("no hay clave para el alias $alias")
        }
        val entry = ks.getEntry(alias, null) as KeyStore.PrivateKeyEntry
        val signature = Signature.getInstance(SIGNATURE_ALGORITHM)
        signature.initSign(entry.privateKey)
        signature.update(payload)
        return base64UrlNoPad(signature.sign())
    }

    /**
     * Verifica una firma base64url contra la publica SPKI del alias actual.
     * Devuelve true/false (nunca lanza por firma invalida).
     */
    fun verify(signatureB64Url: String, payload: ByteArray): Boolean {
        val spki = getPublicKeyOrNull() ?: return false
        return try {
            val pub = parseSpki(spki)
            val sigBytes = Base64.decode(signatureB64Url, Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING)
            val verifier = Signature.getInstance(SIGNATURE_ALGORITHM)
            verifier.initVerify(pub)
            verifier.update(payload)
            verifier.verify(sigBytes)
        } catch (e: Exception) {
            false
        }
    }

    /** Borra el alias de forma inmediata (invalida la clave). */
    fun delete(): Boolean {
        if (!hasAlias()) return false
        try {
            keyStore().deleteEntry(alias)
            return true
        } catch (e: KeyStoreException) {
            return false
        }
    }

    /**
     * Rota el alias: borra la clave actual y genera una nueva. Devuelve el
     * SPKI de la clave NUEVA.
     */
    fun rotate(): String {
        delete()
        return generateOrGetPublicKeySpki()
    }
}
