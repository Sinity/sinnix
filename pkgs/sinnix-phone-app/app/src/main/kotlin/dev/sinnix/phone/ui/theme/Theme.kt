package dev.sinnix.phone.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

/**
 * One look, dark, always.
 *
 * Not a mode. The estate has a visual identity — the hub's violet ops accent,
 * near-black ground, hairline separation — and a phone app that turned white
 * in daylight would read as a different system rather than as the same one in
 * a pocket. [isSystemInDarkTheme] is deliberately not consulted.
 *
 * Dynamic colour is likewise off: Material You would repaint the estate in
 * whatever the wallpaper suggested, and the three status tones here carry
 * meaning that must not drift.
 */
object Palette {
    val Background = Color(0xFF0B0C0D)
    val Surface = Color(0xFF141618)
    val SurfaceHigh = Color(0xFF1B1E21)
    val Hairline = Color(0xFF24282C)
    val Text = Color(0xFFE8E6E3)
    val TextDim = Color(0xFF9AA0A6)
    val TextFaint = Color(0xFF6B7075)

    /** The estate accent. Same violet the hub uses, so the two read as one system. */
    val Accent = Color(0xFF8B7CF6)
    val AccentDim = Color(0xFF5B4FB0)

    /**
     * Status tones. Reserved for capture health, grants and transport — the
     * surfaces where "measured OK" and "assumed OK" are different claims.
     * Nothing else in the app is allowed to speak in these colours, or they
     * stop meaning anything.
     */
    val Evidenced = Color(0xFF6FC28A)
    val Unverified = Color(0xFFD4A84A)
    val Broken = Color(0xFFE05561)

    /** Ribbon fills, which double the status tones at lower saturation. */
    val RibbonCovered = Color(0xFF3E7F5A)
    val RibbonSilent = Color(0xFF8A6B22)
    val RibbonHole = Color(0xFF8C3038)
    val RibbonUnknown = Color(0xFF1E2225)
}

private val SinnixColors =
    darkColorScheme(
        primary = Palette.Accent,
        onPrimary = Color(0xFF12101E),
        primaryContainer = Palette.AccentDim,
        onPrimaryContainer = Palette.Text,
        secondary = Palette.TextDim,
        background = Palette.Background,
        onBackground = Palette.Text,
        surface = Palette.Surface,
        onSurface = Palette.Text,
        surfaceVariant = Palette.SurfaceHigh,
        onSurfaceVariant = Palette.TextDim,
        outline = Palette.Hairline,
        error = Palette.Broken,
        onError = Palette.Text,
    )

/**
 * Monospace for machine state, sans for prose — and the split is semantic, not
 * stylistic. A number the device measured is quoted evidence; a sentence the
 * app wrote is an interpretation. Setting them in different faces means the
 * reader can tell which is which without being told.
 */
private val SinnixTypography =
    Typography(
        displaySmall = TextStyle(fontSize = 34.sp, fontWeight = FontWeight.Light),
        headlineSmall = TextStyle(fontSize = 22.sp, fontWeight = FontWeight.Normal),
        titleMedium = TextStyle(fontSize = 16.sp, fontWeight = FontWeight.Medium),
        bodyMedium = TextStyle(fontSize = 15.sp, fontWeight = FontWeight.Normal),
        bodySmall = TextStyle(fontSize = 13.sp, color = Palette.TextDim),
        labelSmall =
            TextStyle(
                fontSize = 12.sp,
                fontFamily = FontFamily.Monospace,
                color = Palette.TextDim,
            ),
        labelMedium = TextStyle(fontSize = 13.sp, fontFamily = FontFamily.Monospace),
        titleLarge = TextStyle(fontSize = 20.sp, fontWeight = FontWeight.Medium),
    )

@Composable
fun SinnixTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = SinnixColors, typography = SinnixTypography, content = content)
}
