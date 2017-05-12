package org.fountainmc.taco.entities

import com.google.common.collect.ImmutableSet
import net.minecraft.server.Entity
import org.bukkit.craftbukkit.CraftServer
import org.bukkit.craftbukkit.entity.CraftEntity
import org.bukkit.entity.LivingEntity
import org.fountainmc.api.entity.EntityType
import org.fountainmc.api.entity.data.EntityData
import org.fountainmc.api.world.Location
import org.fountainmc.taco.TacoFountainServer
import org.fountainmc.taco.utils.toBukkit
import org.fountainmc.taco.utils.toFountain

class FountainEntity(
        override val server: TacoFountainServer,
        val bukkit: CraftEntity,
        val handle: Entity = bukkit.handle!!
): org.fountainmc.api.entity.Entity {

    //
    // Simple delegates
    //

    override val location: Location
        get() = bukkit.location.toFountain()
    override val isOnGround: Boolean
        get() = bukkit.isOnGround
    override var pitch: Float
        get() = handle.pitch
        set(value) {
            handle.pitch = value
        }
    override var yaw: Float
        get() = handle.yaw
        set(value) {
            handle.yaw = value
        }
    override fun teleport(destination: Location) {
        // May or may not be stealing bukkit's teleport logic
        bukkit.teleport(destination.toBukkit())
    }

    override var primaryPassenger: org.fountainmc.api.entity.Entity?
        get() = bukkit.passenger?.toFountain()
        set(value) {
            if (value != null) {
                bukkit.passenger = value.toBukkit()
            } else {
                bukkit.eject()
            }
        }

    override val passengers: List<FountainEntity>
        get() = bukkit.passengers.map { it.toFountain() }

    override var ticksOnFire: Int
        get() = bukkit.fireTicks
        set(value) {
            bukkit.fireTicks = value
        }

    override fun startRiding(vehicle: org.fountainmc.api.entity.Entity, force: Boolean): Boolean {
        return handle.startRiding((vehicle as FountainEntity).handle, force)
    }

    override var isImmuneToFire: Boolean
        get() = TODO("Not yet implemented!")
        set(value) { TODO("Not yet implemented!") }

    override fun ejectAll() {
        bukkit.eject()
    }

    override fun ejectPassenger(passenger: org.fountainmc.api.entity.Entity) {
        bukkit.removePassenger(passenger.toBukkit())
    }

    override fun dismountVehicle() {
        handle.stopRiding()
    }

    override val vehicle: org.fountainmc.api.entity.Entity?
        get() = bukkit.vehicle.toFountain()

    override fun getNearbyEntities(xRadius: Double, yRadius: Double, zRadius: Double): Set<FountainEntity> {
        return bukkit.getNearbyEntities(xRadius, yRadius, zRadius).mapTo(HashSet()) { it.toFountain() }
    }

    override fun canAcceptPassenger(passenger: org.fountainmc.api.entity.Entity): Boolean {
        return handle.canBeRiddenBy((passenger as FountainEntity).handle)
    }

    override val isDead: Boolean
        get() = bukkit.isDead

    override fun snapshot() = TODO("Not yet implemented!")

    override val entityType: EntityType<*>
        get() = TODO("Not yet implemented!")

    companion object {
        fun createWrapper(entity: CraftEntity): FountainEntity {
            val server = (entity.server as CraftServer).server.fountainServer
            return when (entity) {
                else -> FountainEntity(server, entity)
            }
        }
    }
}