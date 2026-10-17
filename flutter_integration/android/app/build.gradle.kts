import java.util.Properties

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

val releaseSigningPropertiesFile = rootProject.file("key.properties")
val releaseSigningProperties = Properties()
if (releaseSigningPropertiesFile.exists()) {
    releaseSigningPropertiesFile.inputStream().use {
        releaseSigningProperties.load(it)
    }
}
val releaseAdmobAppId = providers.gradleProperty("ADMOB_APP_ID").orNull

android {
    namespace = "com.venapp.app"
    compileSdk = 36
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        applicationId = "com.venapp.app"
        minSdk = 24
        targetSdk = 36
        manifestPlaceholders["admobApplicationId"] =
            "ca-app-pub-3940256099942544~3347511713"
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        create("release") {
            keyAlias = releaseSigningProperties.getProperty("keyAlias")
            keyPassword = releaseSigningProperties.getProperty("keyPassword")
            storeFile = releaseSigningProperties.getProperty("storeFile")
                ?.let { rootProject.file(it) }
            storePassword = releaseSigningProperties.getProperty("storePassword")
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("release")
            manifestPlaceholders["admobApplicationId"] = releaseAdmobAppId ?: ""
        }
    }
}

gradle.taskGraph.whenReady {
    val isReleaseBuild = allTasks.any {
        it.project == project && it.name.contains("Release", ignoreCase = true)
    }
    if (isReleaseBuild) {
        val missingSigningValues = listOf(
            "storeFile",
            "storePassword",
            "keyAlias",
            "keyPassword",
        ).filter { releaseSigningProperties.getProperty(it).isNullOrBlank() }
        val storePath = releaseSigningProperties.getProperty("storeFile")
        val missingAdmobAppId = releaseAdmobAppId.isNullOrBlank() ||
            releaseAdmobAppId == "ca-app-pub-3940256099942544~3347511713"

        if (missingSigningValues.isNotEmpty() ||
            storePath.isNullOrBlank() ||
            !rootProject.file(storePath).isFile ||
            missingAdmobAppId
        ) {
            val missing = buildList {
                if (missingSigningValues.isNotEmpty() ||
                    storePath.isNullOrBlank() ||
                    !rootProject.file(storePath).isFile
                ) {
                    add("a valid android/key.properties and release keystore")
                }
                if (missingAdmobAppId) {
                    add("the production ADMOB_APP_ID Gradle property")
                }
            }
            throw GradleException(
                "Release build blocked: configure ${missing.joinToString(" and ")}. " +
                    "Debug signing and Google's sample AdMob ID are not allowed."
            )
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
