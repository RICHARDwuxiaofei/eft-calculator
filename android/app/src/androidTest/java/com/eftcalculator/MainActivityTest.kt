package com.eftcalculator

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import org.junit.Rule
import org.junit.Test

class MainActivityTest {
    @get:Rule
    val compose = createAndroidComposeRule<MainActivity>()

    @Test
    fun quickPageShowsCoreActionsAndSurvivesRecreation() {
        compose.onNodeWithText("EFT Calculator").assertIsDisplayed()
        compose.onNodeWithText("选择弹药").assertIsDisplayed()
        compose.activityRule.scenario.recreate()
        compose.onNodeWithText("EFT Calculator").assertIsDisplayed()
    }
}
