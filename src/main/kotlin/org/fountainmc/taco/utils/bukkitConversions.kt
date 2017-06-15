package org.fountainmc.taco.utils

import org.bukkit.craftbukkit.CraftWorld
import org.bukkit.craftbukkit.entity.CraftEntity
import org.fountainmc.api.world.Location
import org.fountainmc.taco.TacoFountianWorld
import org.fountainmc.taco.entities.FountainEntity

fun org.bukkit.World.toFountain() = (this as CraftWorld).fountainWorld!!

fun org.bukkit.Location.toFountain(): Location {
    return Location(this.world.toFountain(), this.x, this.y, this.z)
}

fun Location.toBukkit(): org.bukkit.Location {
    return org.bukkit.Location(
            (this.world as TacoFountianWorld).bukkit,
            this.x,
            this.y,
            this.z
    )
}

fun org.bukkit.entity.Entity.toFountain() = (this as CraftEntity).handle.fountainEntity
fun org.fountainmc.api.entity.Entity.toBukkit() = (this as FountainEntity).bukkit
